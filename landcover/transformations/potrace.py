# coding=utf-8
from __future__ import absolute_import, division, print_function

import logging
import json

import numpy as np
from potrace import Bitmap
import rasterio
from rasterio import transform, warp, windows
from rasterio.crs import CRS
import mercantile

from marblecutter.transformations.utils import Transformation

logger = logging.getLogger(__name__)

WGS84_CRS = CRS.from_epsg(4236)

from .colormap import COLORMAP

class Potrace(Transformation):

  def __init__(self):
    super(Potrace, self).__init__(collar=4)

  def postprocess(self, pixels, data_format, offsets):
    # bounds = pixels.bounds.bounds
    # cropped_bounds = crop(pixels, data_format, offsets).bounds.bounds
    return pixels, data_format

  def transform(self, pixels):
    data = pixels.data[0]
    crs = pixels.bounds.crs
    bounds = pixels.bounds.bounds

    # bounds = warp.transform_bounds(
    #     crs, WGS84_CRS, *bounds
    # )

    logger.info("bounds: %s", bounds)
    my, mx = data.shape
    x = bounds[2] - bounds[0]
    y = bounds[3] - bounds[1]
    ox = bounds[0]
    oy = bounds[1]

    
    t = transform.from_bounds(*bounds, mx, my)
    cropped_window = windows.Window(self.collar, self.collar, mx - self.collar, my - self.collar)
    # cropped_bounds = windows.bounds(cropped_window, t)
    # cropped_bounds = (-20037508.342789244, -20037508.342789255, 20037508.342789244, 20037508.342789255)
    cropped_bounds = mercantile.xy_bounds(0, 0, 0)
    logger.info("bounds: %s", bounds)
    logger.info("cropped bounds: %s", cropped_bounds)


    def transformer(c):
        x, y = transform.xy(t, c[1], c[0])

        if x < cropped_bounds[0]:
          x = cropped_bounds[0]

        if x > cropped_bounds[2]:
          x = cropped_bounds[2]

        if y < cropped_bounds[1]:
          y = cropped_bounds[1]

        if y > cropped_bounds[3]:
          y = cropped_bounds[3]

        return (x, y)
        # return (min(max(x, cropped_bounds[0]), cropped_bounds[2]), min(max(y, cropped_bounds[1]), cropped_bounds[3]))

    def reference(vertices):
      # coords = list(map(lambda c: (ox + ((c[0] / mx) * x), oy + ((1 - (c[1] / my)) * y)), vertices))
      # coords = list(map(lambda c: transform.xy(t, c[1], c[0]), vertices))
      # logger.info("vertices: %s", vertices[0])
      # logger.info("mx: %s", mx)
      # logger.info("my: %s", mx)
      # coords = list(map(transformer, filter(lambda xy: 4 <= xy[0] <= mx - 4 or 4 <= xy[1] <= my - 4, vertices)))
      coords = list(map(transformer, vertices))

      if len(coords) > 0 and coords[-1] != coords[0]:
        coords.append(coords[0])

      return coords


    def make_feature(val):
      classification = np.where(data == val, 1, 0)

      bitmap = Bitmap(classification)

      # path = bitmap.trace(turdsize=16, opttolerance=5.0)
      # path = bitmap.trace(turdsize=16)
      path = bitmap.trace(turdsize=2)

      geom = {
        "type": "MultiPolygon",
        "coordinates": [],
      }

      for curve in path.curves_tree:
        vertices = reference(curve.tesselate())
        children = list(map(lambda c: reference(c.tesselate()), curve.children))

        coordinates = [vertices, *children]

        geom["coordinates"].append(coordinates)

      if len(geom["coordinates"]) > 0:
        with rasterio.Env(OGR_ENABLE_PARTIAL_REPROJECTION=True):
          geom = warp.transform_geom(crs, WGS84_CRS, geom)

      return {
        "type": "Feature",
        "geometry": geom,
        "properties": {
          "value": val,
          "fill": "rgb" + str(COLORMAP[val]),
          "stroke-width": 0,
          "fill-opacity": 1
        }
      }

    fc = {
      "type": "FeatureCollection",
      "features": list(filter(lambda x: len(x["geometry"]["coordinates"]) > 0, map(make_feature, COLORMAP.keys())))
    }

    return fc, "GeoJSON"

    # logger.info("fc: %s", json.dumps(fc))

    # logger.info("pixels: %s", pixels)