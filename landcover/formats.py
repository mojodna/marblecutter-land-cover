# coding=utf-8
from __future__ import absolute_import

import json
import logging

import mercantile

import rasterio
from rasterio import features, transform, warp
from rasterio.crs import CRS
from rasterio.rio.helpers import coords

logger = logging.getLogger(__name__)


WGS84_CRS = CRS.from_epsg(4236)


def reproject(shapes, bounds):
    with rasterio.Env(OGR_ENABLE_PARTIAL_REPROJECTION=True):
        for g, val in shapes:
            # TODO this produces garbage on the left edge of the world
            g = warp.transform_geom(bounds.crs, WGS84_CRS, g)
            xs, ys = zip(*coords(g))
            yield {
                "type": "Feature",
                "properties": {"value": val},
                "bbox": [min(xs), min(ys), max(xs), max(ys)],
                "geometry": g,
            }


def GeoJSON(sieve_size=4):
    def _format(pixels, data_format, sources):
        if data_format != "raw":
            raise Exception("Must be raw-formatted")

        _, width, height = pixels.data.shape
        t = transform.from_bounds(*pixels.bounds.bounds, width, height)

        sieved = features.sieve(pixels.data[0], sieve_size)

        # shapes = features.shapes(pixels.data.data, transform=t)
        shapes = features.shapes(sieved, transform=t)

        fs = list(reproject(shapes, pixels.bounds))

        fc = {"type": "FeatureCollection", "features": fs}

        return ("application/json", json.dumps(fc))

    return _format
