# coding=utf-8
from __future__ import print_function

import argparse
import hashlib
import itertools
import json
import logging
import math
import multiprocessing
from bisect import bisect_right
from concurrent import futures
from io import BytesIO
from os import makedirs, path
from time import gmtime
from urllib.parse import urlparse
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import boto3
import botocore
import mercantile
from marblecutter import get_resolution_in_meters, tiling
from marblecutter.catalogs import WGS84_CRS
from marblecutter.catalogs.postgis import PostGISCatalog
from marblecutter.formats.geotiff import GeoTIFF
from marblecutter.stats import Timer
from marblecutter.utils import Bounds
from mercantile import Tile

from ..catalogs import SpatialiteCatalog
from ..colormap import COLORMAP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("botocore.credentials").setLevel(logging.WARNING)
logging.getLogger("marblecutter.mosaic").setLevel(logging.WARNING)
logging.getLogger("rasterio._base").setLevel(logging.WARNING)

CATALOG = PostGISCatalog(table="land_cover")
GEOTIFF_FORMAT = GeoTIFF(colormap=COLORMAP)
S3 = boto3.client("s3")


def build_catalog(tile, min_zoom, max_zoom):
    catalog = SpatialiteCatalog()

    for source in upstream_sources_for_tile(
        tile, CATALOG, min_zoom=min_zoom, max_zoom=max_zoom
    ):
        catalog.add_source(source)

    return catalog


# TODO fold this upstream, e.g. footprints.something
def upstream_sources_for_tile(tile, catalog, min_zoom=None, max_zoom=None):
    """Render a tile's source footprints."""
    bounds = Bounds(mercantile.bounds(tile), WGS84_CRS)
    shape = (256, 256)
    resolution = get_resolution_in_meters(bounds, shape)

    return catalog.get_sources(
        bounds,
        resolution,
        min_zoom=min_zoom,
        max_zoom=max_zoom,
        include_geometries=True,
    )


def generate_tiles(tile, max_zoom, metatile=1, materialize_zooms=None):
    tiles = []
    metatile = min(metatile, 2 ** tile.z)

    for dx in range(0, metatile):
        for dy in range(0, metatile):
            tiles.append(Tile(tile.x + dx, tile.y + dy, tile.z))

    for z in range(tile.z, max_zoom + 1):
        if materialize_zooms is None or z in materialize_zooms:
            a, tiles = itertools.tee(tiles, 2)

            yield from a

        tiles = itertools.chain.from_iterable(mercantile.children(t) for t in tiles)


def subpyramids(tile, max_zoom, metatile=1, materialize_zooms=None):
    return filter(lambda t: t.x % metatile == 0 and t.y % metatile == 0, generate_tiles(tile, max_zoom, metatile, materialize_zooms))


def create_archive(tiles, root, max_zoom, meta):
    meta["minzoom"] = root.z
    meta["maxzoom"] = max_zoom
    # TODO this is wrong; should account for metatiles
    meta["bounds"] = mercantile.bounds(root)
    meta["root"] = "{}/{}/{}".format(root.z, root.x, root.y)

    date_time = gmtime()[0:6]
    out = BytesIO()

    with ZipFile(out, "w", ZIP_DEFLATED, allowZip64=True) as archive:
        archive.comment = json.dumps(meta).encode("utf-8")

        for tile, (_, data) in tiles:
            logger.info("%d/%d/%d", tile.z, tile.x, tile.y)

            info = ZipInfo("{}/{}/{}@2x.tif".format(tile.z, tile.x, tile.y), date_time)
            info.external_attr = 0o755 << 16
            archive.writestr(info, data, ZIP_DEFLATED)

    return out.getvalue()


def write(body, target):
    url = urlparse(target)

    if url.scheme in ("", "file"):
        target = path.abspath(url.netloc + url.path)

        if not path.isdir(path.dirname(target)):
            makedirs(path.dirname(target))

        with open(target, "wb") as archive:
            archive.write(body)
    elif url.scheme == "s3":
        bucket = url.netloc
        key = url.path[1:]

        try:
            S3.put_object(
                Body=body,
                Bucket=bucket,
                Key=key,
                ContentType="image/tiff",
            )
        except botocore.exceptions.ClientError as e:
            logger.exception(e)


def power_of_2(value):
    value = int(value)

    if math.floor(math.log2(value)) != math.ceil(math.log2(value)):
        raise argparse.ArgumentTypeError("%s must be a power of 2" % value)

    return value


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-x", type=int, required=True)
    parser.add_argument("-y", type=int, required=True)
    parser.add_argument("--zoom", "-z", type=int, required=True)
    parser.add_argument("--max-zoom", "-Z", type=int, required=True)
    parser.add_argument("--materialize", "-m", type=int, action="append")
    parser.add_argument("--metatile", "-M", type=power_of_2, default=1)
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument(
        "--concurrency", "-c", type=int, default=multiprocessing.cpu_count() * 2
    )
    parser.add_argument("--hash", "-H", action="store_true")
    parser.add_argument("--cache-sources", "-l", action="store_true")
    parser.add_argument("target", default="file://./", nargs="?")

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    root = Tile(args.x, args.y, args.zoom)
    concurrency = args.concurrency
    min_zoom = args.zoom
    max_zoom = args.max_zoom
    metatile = args.metatile
    materialize_zooms = args.materialize or []
    if args.zoom not in materialize_zooms:
        materialize_zooms = [args.zoom] + materialize_zooms

    if args.cache_sources:
        logger.info(
            "Caching sources for root tile %s from zoom %d to %d", root, min_zoom, max_zoom
        )
        catalog = build_catalog(root, min_zoom, max_zoom)
    else:
        catalog = CATALOG

    def render(tile_with_sources):
        tile, sources = tile_with_sources

        with Timer() as t:
            headers, data = tiling.render_tile_from_sources(
                tile, sources, format=GEOTIFF_FORMAT, scale=2
            )

        logger.debug(
            "(%d/%d/%d) Took %.03fs to render tile (%s bytes), %s",
            tile.z,
            tile.x,
            tile.y,
            t.elapsed,
            len(data),
            headers.get("Server-Timing"),
        )

        return (tile, (headers, data))

    def sources_for_tile(tile):
        """Render a tile's source footprints."""
        bounds = Bounds(mercantile.bounds(tile), WGS84_CRS)
        # TODO scale
        shape = (512, 512)
        resolution = get_resolution_in_meters(bounds, shape)

        # convert sources to a list to avoid passing the generator across thread boundaries
        return (tile, list(catalog.get_sources(bounds, resolution)))

    meta = {
        "name": "Land Cover",
        "description": "Unified land cover, derived from MODIS-LC, ESACCI-LC, NLCD, and C-CAP.",
        "minzoom": min_zoom,
        "maxzoom": max_zoom,
        "bounds": mercantile.bounds(root),
        "formats": {"tif": "image/tiff"},
        "minscale": 2,
        "maxscale": 2,
    }

    if metatile > 1:
        meta["metatile"] = metatile

    source = path.join(args.target, "{z}", "{x}", "{y}.zip")
    if args.hash:
        source = path.join(args.target, "{h}", "{z}", "{x}", "{y}.zip")

    root_meta = meta.copy()
    root_meta["materializedZooms"] = materialize_zooms
    root_meta["source"] = source

    write(json.dumps(root_meta), path.join(args.target, "meta.json"))

    with futures.ProcessPoolExecutor(max_workers=concurrency) as executor:
        for materialized_tile in subpyramids(root, args.max_zoom, metatile, materialize_zooms):
            # find the next materialized zoom
            idx = bisect_right(materialize_zooms, materialized_tile.z)
            if idx != len(materialize_zooms):
                # treat the zoom before the next materialized zoom as the max
                max_zoom = materialize_zooms[idx] - 1
            else:
                # out of materialized zooms
                max_zoom = args.max_zoom

            logger.info("Rendering %d/%d/%d to zoom %d", materialized_tile.z, materialized_tile.x, materialized_tile.y, max_zoom)

            tiles = executor.map(
                render, map(sources_for_tile, generate_tiles(materialized_tile, max_zoom, metatile))
            )

            archive = create_archive(tiles, materialized_tile, max_zoom, meta.copy())

            key = "{}/{}/{}".format(materialized_tile.z, materialized_tile.x, materialized_tile.y)
            if args.hash:
                h = hashlib.md5(key.encode("utf-8")).hexdigest()[:5]
                key = "{}/{}".format(h, key)

            write(archive, path.join(args.target, "{}.zip".format(key)))