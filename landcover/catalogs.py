# coding=utf-8
import json
import logging
import traceback

import dateutil.parser

from pysqlite3 import dbapi2 as sqlite3
from marblecutter import get_zoom
from marblecutter.catalogs import WGS84_CRS, Catalog
from marblecutter.utils import Bounds, Source
from rasterio import warp

Infinity = float("inf")
LOG = logging.getLogger(__name__)


class SpatialiteCatalog(Catalog):
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        # self.conn = sqlite3.connect("/tmp/catalog.sqlite3")
        self.conn.enable_load_extension(True)
        self.conn.execute("SELECT load_extension('mod_spatialite')")

        cursor = self.conn.cursor()

        try:
            cursor.execute("SELECT InitSpatialMetadata()")

            cursor.execute(
                """
CREATE TABLE footprints (
  source text,
  filename character varying,
  url text,
  resolution double precision,
  min_zoom integer,
  max_zoom integer,
  priority double precision,
  meta text,
  recipes text,
  band_info text,
  acquired_at timestamp
)
      """
            )

            cursor.execute(
                "SELECT AddGeometryColumn('footprints', 'geom', 4326, 'MULTIPOLYGON', 'XY')"
            )
            cursor.execute("SELECT CreateSpatialIndex('footprints', 'geom')")
            cursor.execute(
                "SELECT AddGeometryColumn('footprints', 'mask', 4326, 'MULTIPOLYGON', 'XY')"
            )
            cursor.execute("SELECT CreateSpatialIndex('footprints', 'mask')")

            self.conn.commit()
        except Exception as e:
            LOG.exception(e)
            raise e
        finally:
            cursor.close()

    def add_source(self, source):
        cursor = self.conn.cursor()

        try:
            cursor.execute(
                """
INSERT INTO footprints (
  source,
  filename,
  url,
  resolution,
  min_zoom,
  max_zoom,
  priority,
  meta,
  recipes,
  band_info,
  acquired_at,
  geom,
  mask
) VALUES (
  ?,
  ?,
  ?,
  ?,
  ?,
  ?,
  ?,
  ?,
  ?,
  ?,
  date(?),
  SetSRID(GeomFromGeoJSON(?), 4326),
  SetSRID(GeomFromGeoJSON(?), 4326)
)
      """,
                (
                    source.name,
                    source.filename,
                    source.url,
                    source.resolution,
                    source.min_zoom,
                    source.max_zoom,
                    source.priority,
                    json.dumps(source.meta),
                    json.dumps(source.recipes),
                    json.dumps(source.band_info),
                    None
                    if source.acquired_at is None
                    else dateutil.parser.parse(str(source.acquired_at)).isoformat(),
                    json.dumps(source.geom),
                    json.dumps(source.mask),
                ),
            )

            self.conn.commit()
        except Exception as e:
            LOG.exception(e)
            raise e
        finally:
            cursor.close()

    def get_sources(self, bounds, resolution):
        cursor = self.conn.cursor()

        # TODO this is becoming relatively standard catalog boilerplate
        zoom = get_zoom(max(resolution))
        if bounds.crs == WGS84_CRS:
            left, bottom, right, top = bounds.bounds
        else:
            left, bottom, right, top = warp.transform_bounds(
                bounds.crs, WGS84_CRS, *bounds.bounds
            )

        left = left if left != Infinity else -180
        bottom = bottom if bottom != Infinity else -90
        right = right if right != Infinity else 180
        top = top if top != Infinity else 90

        try:
            query = """
WITH bbox AS (
  SELECT SetSRID(GeomFromGeoJSON(?), 4326) geom
),
uncovered AS (
  SELECT SetSRID(GeomFromGeoJSON(?), 4326) geom
),
date_range AS (
  SELECT
  COALESCE(min(acquired_at), date('1970-01-01')) min,
  COALESCE(max(acquired_at), date('1970-01-01')) max
  FROM footprints
)
SELECT
  url,
  source,
  resolution,
  coalesce(band_info, '{{}}') band_info,
  coalesce(meta, '{{}}') meta,
  coalesce(recipes, '{{}}') recipes,
  acquired_at,
  null band, -- for Source constructor compatibility
  priority,
  ST_Area(ST_Intersection(uncovered.geom, footprints.geom)) /
  ST_Area(bbox.geom) coverage,
  AsGeoJSON(footprints.geom) geom,
  AsGeoJSON(ST_Difference(uncovered.geom, footprints.geom)) uncovered
FROM bbox, date_range, footprints
JOIN uncovered ON ST_Intersects(footprints.geom, uncovered.geom)
WHERE footprints.url NOT IN ({url_placeholders})
  AND ? BETWEEN min_zoom AND max_zoom
ORDER BY
  10 * coalesce(footprints.priority, 0.5) *
  .1 * (1 - (strftime('%s') -
         strftime('%s', COALESCE(acquired_at, date('2000-01-01')))) /
        (strftime('%s') - strftime('%s', date_range.min))) *
  50 *
    -- de-prioritize over-zoomed sources
    CASE WHEN ? / footprints.resolution >= 1
    THEN 1
    ELSE 1 / footprints.resolution
    END *
  ST_Area(
    ST_Intersection(bbox.geom, footprints.geom)) /
    ST_Area(bbox.geom) DESC
LIMIT 1
      """

            bbox = json.dumps(
                {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [left, bottom],
                            [left, top],
                            [right, top],
                            [right, bottom],
                            [left, bottom],
                        ]
                    ],
                }
            )

            uncovered = bbox
            urls = set()

            while True:
                url_placeholders = ", ".join("?" * len(urls))
                cursor.execute(
                    query.format(url_placeholders=url_placeholders),
                    (bbox, uncovered) + tuple(urls) + (zoom, min(resolution)),
                )

                count = 0
                for record in cursor:
                    count += 1
                    (
                        url,
                        source,
                        res,
                        band_info,
                        meta,
                        recipes,
                        acquired_at,
                        band,
                        priority,
                        coverage,
                        geom,
                        uncovered,
                    ) = record

                    yield Source(
                        url,
                        source,
                        res,
                        json.loads(band_info),
                        json.loads(meta),
                        json.loads(recipes),
                        acquired_at,
                        band,
                        priority,
                        coverage,
                    )

                    urls.add(url)

                if count == 0 or uncovered is None:
                    break

        except Exception as e:
            LOG.exception(e)
        finally:
            cursor.close()
