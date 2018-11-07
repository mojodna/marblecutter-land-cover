# coding=utf-8
from __future__ import absolute_import

import logging
from urllib.parse import urlencode
from logging import StreamHandler

from cachetools.func import lru_cache
from flask import Markup, jsonify, render_template, request
from marblecutter import NoCatalogAvailable, tiling
from marblecutter.catalogs.postgis import PostGISCatalog
from marblecutter.formats.geotiff import GeoTIFF
from marblecutter.formats.png import PNG
from marblecutter.transformations import Colormap, Image
from marblecutter.web import app, url_for
from mercantile import Tile

from .colormap import COLORMAP
from .formats import GeoJSON

LOG = logging.getLogger(__name__)
CATALOG = PostGISCatalog(table="land_cover")
COLORMAP_TRANSFORMATION = Colormap(COLORMAP)
IMAGE_TRANSFORMATION = Image()
IMAGE_FORMAT = PNG()
GEOTIFF_FORMAT = GeoTIFF(colormap=COLORMAP)

# configure logging

logging.basicConfig(level=logging.INFO)
logging.getLogger("rasterio._base").setLevel(logging.WARNING)
logging.getLogger("botocore.credentials").setLevel(logging.WARNING)


import mercantile
from marblecutter import get_resolution_in_meters
from marblecutter.utils import Bounds
from marblecutter.catalogs import WGS84_CRS
from marblecutter.tiling import WEB_MERCATOR_CRS
from .catalogs import SpatialiteCatalog

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
    shape = (512, 512)
    resolution = get_resolution_in_meters(bounds, shape)

    return catalog.get_sources(
        bounds,
        resolution,
        min_zoom=min_zoom,
        max_zoom=max_zoom,
        include_geometries=True,
    )

LOCAL_CATALOG = build_catalog(Tile(0, 0, 0), 0, 7)


@app.route("/")
def meta():
    meta = {
        "bounds": CATALOG.bounds,
        "center": CATALOG.center,
        "maxzoom": CATALOG.maxzoom,
        "minzoom": CATALOG.minzoom,
        "name": CATALOG.name,
        "tilejson": "2.2.0",
        "tiles": [
            "{}{{z}}/{{x}}/{{y}}?{}".format(
                url_for("meta", _external=True, _scheme=""), urlencode(request.args)
            )
        ],
    }

    return jsonify(meta)


@app.route("/preview")
def preview():
    return (
        render_template(
            "preview.html",
            tilejson_url=Markup(
                url_for("meta", _external=True, _scheme="", **request.args)
            ),
        ),
        200,
        {"Content-Type": "text/html"},
    )


@app.route("/local/")
def local_meta():
    meta = {
        "bounds": LOCAL_CATALOG.bounds,
        "center": LOCAL_CATALOG.center,
        "maxzoom": LOCAL_CATALOG.maxzoom,
        "minzoom": LOCAL_CATALOG.minzoom,
        "name": LOCAL_CATALOG.name,
        "tilejson": "2.2.0",
        "tiles": [
            "{}{{z}}/{{x}}/{{y}}?{}".format(
                url_for("local_meta", _external=True, _scheme=""), urlencode(request.args)
            )
        ],
    }

    return jsonify(meta)


@app.route("/local/preview")
def local_preview():
    return (
        render_template(
            "preview.html",
            tilejson_url=Markup(
                url_for("local_meta", _external=True, _scheme="", **request.args)
            ),
        ),
        200,
        {"Content-Type": "text/html"},
    )


@app.route("/<int:z>/<int:x>/<int:y>")
@app.route("/<int:z>/<int:x>/<int:y>@<int:scale>x")
def render_png(z, x, y, scale=1):
    tile = Tile(x, y, z)

    headers, data = tiling.render_tile(
        tile,
        CATALOG,
        format=IMAGE_FORMAT,
        transformation=COLORMAP_TRANSFORMATION,
        scale=scale,
    )

    headers.update(CATALOG.headers)

    return data, 200, headers


@app.route("/<int:z>/<int:x>/<int:y>.json")
def render_json(z, x, y, scale=1):
    tile = Tile(x, y, z)

    sieve = int(request.args.get("sieve", 4))

    headers, data = tiling.render_tile(
        tile,
        CATALOG,
        format=GeoJSON(sieve_size=sieve),
        scale=scale,
    )

    headers.update(CATALOG.headers)

    return data, 200, headers


@app.route("/local/<int:z>/<int:x>/<int:y>")
@app.route("/local/<int:z>/<int:x>/<int:y>@<int:scale>x")
def local_render_png(z, x, y, scale=1):
    tile = Tile(x, y, z)

    # bounds = Bounds(mercantile.bounds(tile), WGS84_CRS)
    bounds = Bounds(mercantile.xy_bounds(tile), WEB_MERCATOR_CRS)
    # TODO scale
    if scale == 2:
        shape = (512, 512)
    else:
        shape = (256, 256)

    LOG.info("bounds: %s", bounds)
    LOG.info("shape: %s", shape)
    resolution = get_resolution_in_meters(bounds, shape)

    sources = LOCAL_CATALOG.get_sources(bounds, resolution)

    headers, data = tiling.render_tile_from_sources(
        tile,
        sources,
        format=IMAGE_FORMAT,
        transformation=COLORMAP_TRANSFORMATION,
        scale=scale,
    )

    headers.update(LOCAL_CATALOG.headers)

    return data, 200, headers


@app.route("/<int:z>/<int:x>/<int:y>.tif")
def render_tif(z, x, y):
    tile = Tile(x, y, z)

    headers, data = tiling.render_tile(tile, CATALOG, format=GEOTIFF_FORMAT)

    headers.update(CATALOG.headers)

    return data, 200, headers


@app.route("/raw/")
def raw_meta():
    meta = {
        "bounds": CATALOG.bounds,
        "center": CATALOG.center,
        "maxzoom": CATALOG.maxzoom,
        "minzoom": CATALOG.minzoom,
        "name": CATALOG.name,
        "tilejson": "2.2.0",
        "tiles": [
            "{}{{z}}/{{x}}/{{y}}?{}".format(
                url_for("raw_meta", _external=True, _scheme=""), urlencode(request.args)
            )
        ],
    }

    return jsonify(meta)


@app.route("/raw/preview")
def raw_preview():
    return (
        render_template(
            "preview.html",
            tilejson_url=Markup(
                url_for("raw_meta", _external=True, _scheme="", **request.args)
            ),
        ),
        200,
        {"Content-Type": "text/html"},
    )


@app.route("/raw/<int:z>/<int:x>/<int:y>")
@app.route("/raw/<int:z>/<int:x>/<int:y>@<int:scale>x")
def raw_render_png(z, x, y, scale=1):
    tile = Tile(x, y, z)

    headers, data = tiling.render_tile(
        tile,
        CATALOG,
        format=IMAGE_FORMAT,
        transformation=IMAGE_TRANSFORMATION,
        expand="meta",
        scale=scale,
    )

    headers.update(CATALOG.headers)

    return data, 200, headers


@app.route("/raw/<int:z>/<int:x>/<int:y>.tif")
def raw_render_tif(z, x, y):
    tile = Tile(x, y, z)

    headers, data = tiling.render_tile(
        tile, CATALOG, format=GEOTIFF_FORMAT, expand="meta"
    )

    headers.update(CATALOG.headers)

    return data, 200, headers
