"""Explicit raw-DN conversion, masks and traceable cell summaries."""
import os
from pathlib import Path
import uuid

import numpy as np
import pandas as pd
import rasterio


def reflectance(raw, scale, offset, nodata=0):
    raw = np.ma.asarray(raw, dtype="float32")
    arr = raw.filled(np.nan)
    invalid = np.ma.getmaskarray(raw) | ~np.isfinite(arr) | (arr == 0)
    if nodata is not None:
        invalid |= arr == nodata
    out = arr * float(scale) + float(offset)
    out[invalid | (out < 0)] = np.nan
    return out


def ndvi(red, nir, epsilon=1e-6):
    red, nir = np.asarray(red), np.asarray(nir)
    denominator = nir + red
    valid = np.isfinite(red) & np.isfinite(nir) & (red >= 0) & (nir >= 0) & (denominator > epsilon)
    out = np.full(red.shape, np.nan, dtype="float32")
    np.divide(nir - red, denominator, out=out, where=valid)
    return out


def block_stats(labels, values, count):
    good = (labels > 0) & np.isfinite(values)
    counts = np.bincount(labels[good], minlength=count + 1)[1:]
    sums = np.bincount(labels[good], weights=values[good], minlength=count + 1)[1:]
    means = np.divide(sums, counts, out=np.full(count, np.nan), where=counts > 0)
    return means, counts


def scene_rows(item, red, nir, scl, grid, cfg):
    if any(a.shape != grid.labels.shape for a in (red, nir, scl)):
        raise ValueError("All bands must share the exact target grid.")
    index = ndvi(red, nir, cfg["quality"]["denominator_epsilon"])
    index[~np.isin(scl, cfg["quality"]["scl_keep"]) | (grid.labels == 0)] = np.nan
    means, counts = block_stats(grid.labels, index, len(grid.ids))
    date = pd.Timestamp(item["properties"]["datetime"]).tz_convert("UTC").tz_localize(None)
    rows = pd.DataFrame({"item_id": item["id"], "date": date.isoformat(), "block_id": grid.ids,
                         "ndvi_mean": means, "valid_px": counts, "total_px": grid.totals,
                         "valid_fraction": counts / grid.totals,
                         "cloud_cover": item["properties"].get("eo:cloud_cover")})
    return rows, index


def write_ndvi(path, index, grid):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.stem + "." + uuid.uuid4().hex + ".tmp.tif")
    try:
        with rasterio.open(temp, "w", driver="GTiff", width=index.shape[1], height=index.shape[0],
                           count=1, dtype="float32", crs=grid.crs, transform=grid.transform,
                           nodata=-9999.0, compress="deflate", tiled=True) as dst:
            dst.write(np.where(np.isfinite(index), index, -9999).astype("float32"), 1)
            dst.update_tags(description="SCL-masked NDVI; dimensionless; no crop stress diagnosis")
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()
