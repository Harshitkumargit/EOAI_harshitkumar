"""One fixed metre-based grid; no shapely/geopandas/pyproj dependency."""
from dataclasses import dataclass
import math

import numpy as np
from rasterio.features import rasterize, shapes
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds, transform_geom


def bbox_geometry(bbox):
    x0, y0, x1, y1 = bbox
    return {"type": "Polygon", "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]}


@dataclass
class Grid:
    labels: np.ndarray
    transform: object
    crs: str
    cells: list
    totals: np.ndarray

    @property
    def ids(self):
        return [c["properties"]["block_id"] for c in self.cells]


def make_grid(cfg):
    a = cfg["aoi"]
    res, size, crs = a["resolution_m"], a["cell_size_m"], a["crs"]
    bounds = transform_bounds("EPSG:4326", crs, *a["bbox"], densify_pts=21)
    left, bottom = (math.floor(v / res) * res for v in bounds[:2])
    right, top = (math.ceil(v / res) * res for v in bounds[2:])
    width, height = int(round((right - left) / res)), int(round((top - bottom) / res))
    if width * height > 16_000_000:
        raise ValueError("AOI raster exceeds 16 million pixels; shrink the AOI or increase resolution.")
    affine = from_origin(left, top, res, res)
    polygon = transform_geom("EPSG:4326", crs, bbox_geometry(a["bbox"]))
    inside = rasterize([(polygon, 1)], out_shape=(height, width), transform=affine, dtype="uint8")
    pp = int(size // res)
    columns = math.ceil(width / pp)
    lab = (np.arange(height)[:, None] // pp * columns + np.arange(width)[None, :] // pp + 1).astype("int32")
    lab[inside == 0] = 0
    present = np.unique(lab[lab > 0])
    remap = np.zeros(int(lab.max()) + 1, dtype="int32")
    remap[present] = np.arange(1, len(present) + 1)
    lab = remap[lab]
    totals = np.bincount(lab.ravel(), minlength=len(present) + 1)[1:]
    geometries = {}
    for geom, value in shapes(lab, mask=lab > 0, transform=affine):
        geometries.setdefault(int(value), []).append(geom)
    cells = []
    for number in range(1, len(present) + 1):
        parts = geometries[number]
        geom = parts[0] if len(parts) == 1 else {"type": "MultiPolygon", "coordinates": [g["coordinates"] for g in parts]}
        cells.append({"type": "Feature", "geometry": transform_geom(crs, "EPSG:4326", geom, precision=7),
                      "properties": {"block_id": f"B{number:03d}", "total_px": int(totals[number - 1]),
                                     "area_km2": float(totals[number - 1] * res * res / 1e6)}})
    return Grid(lab, affine, crs, cells, totals)
