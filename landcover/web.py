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
from marblecutter.transformations import Colormap, Image, Transformation
from marblecutter.web import app, url_for
from mercantile import Tile

from .colormap import COLORMAP
from .formats import GeoJSON

LOG = logging.getLogger(__name__)
CATALOG = PostGISCatalog(table="land_cover")
COLORMAP_TRANSFORMATION = Colormap(COLORMAP)
IMAGE_TRANSFORMATION = Image()
IMAGE_FORMAT = PNG(paletted=True)
GEOTIFF_FORMAT = GeoTIFF(colormap=COLORMAP)

# configure logging

logging.basicConfig(level=logging.INFO)
logging.getLogger("rasterio._base").setLevel(logging.WARNING)
logging.getLogger("botocore.credentials").setLevel(logging.WARNING)


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
def render_json(z, x, y):
    tile = Tile(x, y, z)

    sieve = int(request.args.get("sieve", 4))

    headers, data = tiling.render_tile(
        tile,
        CATALOG,
        format=GeoJSON(sieve_size=sieve),
        transformation=Transformation(collar=8),
        scale=0.5,
    )

    headers.update(CATALOG.headers)

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
