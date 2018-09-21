# coding=utf-8
from __future__ import absolute_import

import logging
from urllib.parse import urlencode
from logging import StreamHandler

from cachetools.func import lru_cache
from flask import Markup, jsonify, render_template, request, url_for
from marblecutter import NoCatalogAvailable, tiling
from marblecutter.catalogs.postgis import PostGISCatalog
from marblecutter.formats.geotiff import GeoTIFF
from marblecutter.formats.png import PNG
from marblecutter.transformations import Colormap
from marblecutter.web import app
from mercantile import Tile

nothing = 0
water = 10
developed = 20
barren = 30
forest = 40
shrubland = 50
herbaceous = 70
cultivated = 80
wetlands = 90

COLORMAP = {
    water: (69, 128, 162),
    forest: (27, 119, 28),
    shrubland: (173, 164, 127),
    herbaceous: (188, 212, 149),
    wetlands: (146, 184, 186),
    cultivated: (215, 214, 114),
    developed: (203, 8, 20),
    barren: (198, 180, 134),
}

LOG = logging.getLogger(__name__)
CATALOG = PostGISCatalog(table="land_cover")
COLORMAP_TRANSFORMATION = Colormap(COLORMAP)
IMAGE_FORMAT = PNG()
GEOTIFF_FORMAT = GeoTIFF(colormap=COLORMAP)

# configure logging

logging.basicConfig(level=logging.INFO)
logging.getLogger("rasterio._base").setLevel(logging.WARNING)
logging.getLogger("botocore.credentials").setLevel(logging.WARNING)


def make_prefix():
    host = request.headers.get("X-Forwarded-Host", request.headers.get("Host", ""))

    # sniff for API Gateway
    if ".execute-api." in host and ".amazonaws.com" in host:
        return request.headers.get("X-Stage")


@app.route("/tiles/")
@app.route("/<prefix>/tiles/")
def meta(prefix=None):
    meta = {
        "bounds": CATALOG.bounds,
        "center": CATALOG.center,
        "maxzoom": CATALOG.maxzoom,
        "minzoom": CATALOG.minzoom,
        "name": CATALOG.name,
        "tilejson": "2.2.0",
        "tiles": [
            "{}{{z}}/{{x}}/{{y}}?{}".format(
                url_for("meta", prefix=make_prefix(), _external=True, _scheme=""),
                urlencode(request.args),
            )
        ],
    }

    return jsonify(meta)


@app.route("/preview")
@app.route("/<prefix>/preview")
def preview(prefix=None):
    return (
        render_template(
            "preview.html",
            tilejson_url=Markup(
                url_for(
                    "meta",
                    prefix=make_prefix(),
                    _external=True,
                    _scheme="",
                    **request.args
                )
            ),
        ),
        200,
        {"Content-Type": "text/html"},
    )


@app.route("/tiles/<int:z>/<int:x>/<int:y>")
@app.route("/tiles/<int:z>/<int:x>/<int:y>@<int:scale>x")
@app.route("/<prefix>/tiles/<int:z>/<int:x>/<int:y>")
@app.route("/<prefix>/tiles/<int:z>/<int:x>/<int:y>@<int:scale>x")
def render_png(z, x, y, scale=1, prefix=None):
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


@app.route("/tiles/<int:z>/<int:x>/<int:y>.tif")
@app.route("/<prefix>/tiles/<int:z>/<int:x>/<int:y>.tif")
def render_tif(z, x, y, prefix=None):
    tile = Tile(x, y, z)

    headers, data = tiling.render_tile(tile, CATALOG, format=GEOTIFF_FORMAT)

    headers.update(CATALOG.headers)

    return data, 200, headers
