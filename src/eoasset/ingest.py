"""Public Earth Search v1 STAC -> aligned COG pixels -> transactional cache."""
import json
import logging
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlsplit, urlunsplit
from urllib.request import Request, urlopen

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT

from .preprocess import reflectance, scene_rows, write_ndvi
from .util import digest

LOG = logging.getLogger(__name__)

COG_HOST = "sentinel-cogs.s3.us-west-2.amazonaws.com"
COG_ENDPOINT_MODES = ("regional_path", "dualstack_path", "virtual", "dualstack_virtual")


def _cog_href(href, mode):
    """Switch only the known public Sentinel COG host between equivalent AWS endpoints."""
    parts = urlsplit(href)
    if parts.hostname != COG_HOST:
        return href
    key = parts.path.lstrip("/")
    if mode == "regional_path":
        host, path = "s3.us-west-2.amazonaws.com", "/sentinel-cogs/" + key
    elif mode == "dualstack_path":
        host, path = "s3.dualstack.us-west-2.amazonaws.com", "/sentinel-cogs/" + key
    elif mode == "virtual":
        host, path = COG_HOST, parts.path
    elif mode == "dualstack_virtual":
        host, path = "sentinel-cogs.s3.dualstack.us-west-2.amazonaws.com", parts.path
    else:
        raise ValueError(f"Unknown COG endpoint mode: {mode}")
    return urlunsplit((parts.scheme, host, path, parts.query, parts.fragment))


def _transient_raster_error(exc):
    chain, seen = [], set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        chain.append(str(exc).lower())
        exc = exc.__cause__ or exc.__context__
    message = " | ".join(chain)
    return any(token in message for token in (
        "could not resolve host", "resolve host", "temporary failure in name resolution",
        "name or service not known", "connection reset", "connection refused",
        "failed to connect", "network is unreachable", "timed out", "timeout",
        "proxy error", "http 429", "http 500", "http 502", "http 503", "http 504",
        "response_code=0", "tiffreadencodedtile", "ireadblock failed",
        "read failed. see previous exception",
    ))


def request_json(url, cfg, body=None, method=None):
    if urlparse(url).scheme != "https":
        raise ValueError("STAC HTTP requests require HTTPS.")
    encoded = json.dumps(body).encode() if body is not None else None
    request = Request(url, data=encoded, method=method or ("POST" if body is not None else "GET"),
                      headers={"Content-Type": "application/json", "User-Agent": "PunjabVegetationWatch/1.0"})
    for attempt in range(cfg["stac"]["attempts"]):
        try:
            with urlopen(request, timeout=cfg["stac"]["timeout_seconds"]) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError) as exc:
            if isinstance(exc, HTTPError) and exc.code not in (408, 429, 500, 502, 503, 504):
                raise
            if attempt + 1 == cfg["stac"]["attempts"]:
                raise
            time.sleep(min(2 ** attempt, 4))


def search_items(cfg, max_items=None):
    body = {"collections": [cfg["stac"]["collection"]], "bbox": cfg["aoi"]["bbox"],
            "datetime": f"{cfg['time']['start']}T00:00:00Z/{cfg['time']['end']}T23:59:59Z",
            "query": {"eo:cloud_cover": {"lte": cfg["stac"]["max_cloud"]}}, "limit": 100}
    url, method, seen_pages, items = cfg["stac"]["url"] + "/search", "POST", set(), {}
    while url:
        key = digest({"url": url, "body": body, "method": method})
        if key in seen_pages:
            raise RuntimeError("STAC pagination repeated a page; refusing incomplete discovery.")
        seen_pages.add(key)
        page = request_json(url, cfg, body, method)
        if "features" not in page:
            raise ValueError("STAC search response has no features array.")
        for item in page["features"]:
            items[item["id"]] = item
        nxt = next((link for link in page.get("links", []) if link["rel"] == "next"), None)
        if not nxt:
            break
        url, method = nxt["href"], nxt.get("method", "GET").upper()
        if method == "POST":
            body = {**(body or {}), **nxt.get("body", {})} if nxt.get("merge") else nxt.get("body", {})
        else:
            body = None
    ordered = sorted(items.values(), key=lambda i: (i["properties"]["datetime"], i["id"]))
    # Same discovery subset on every trial, before removing cached scenes.
    return ordered[:max_items] if max_items is not None else ordered


def source_hash(item):
    return digest({"id": item["id"], "collection": item.get("collection"), "geometry": item.get("geometry"),
                   "properties": item["properties"], "assets": item["assets"]})


def asset_metadata(item, band):
    try:
        asset = item["assets"][band]
    except KeyError as exc:
        raise ValueError(f"{item.get('id')}: required asset {band!r} missing") from exc
    href = asset["href"]
    if not href.startswith("https://") or not ("tif" in asset.get("type", "").lower() or urlparse(href).path.lower().endswith((".tif", ".tiff"))):
        raise ValueError(f"{band}: expected public HTTPS GeoTIFF COG asset.")
    rb = (asset.get("raster:bands") or [{}])[0]
    if band != "scl" and "scale" not in rb:
        raise ValueError(f"{band}: explicit raster:bands scale missing; do not guess from pixel magnitude.")
    scale, offset = float(rb.get("scale", 1)), float(rb.get("offset", 0))
    if not np.isfinite(scale) or scale <= 0 or not np.isfinite(offset):
        raise ValueError(f"Invalid radiometric metadata for {band}.")
    return {"href": href, "scale": scale, "offset": offset, "nodata": rb.get("nodata", 0)}


def load_scene(item, grid, cfg, endpoint_mode="regional_path"):
    arrays, metadata = {}, {}
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MAX_RETRY=3,
                      GDAL_HTTP_RETRY_DELAY=1, GDAL_HTTP_TIMEOUT=cfg["stac"]["timeout_seconds"]):
        for band in ("red", "nir", "scl"):
            meta = asset_metadata(item, band)
            meta = {**meta, "source_href": meta["href"], "href": _cog_href(meta["href"], endpoint_mode)}
            metadata[band] = meta
            with rasterio.open(meta["href"]) as src:
                with WarpedVRT(src, crs=grid.crs, transform=grid.transform,
                               width=grid.labels.shape[1], height=grid.labels.shape[0],
                               src_nodata=src.nodata if src.nodata is not None else meta["nodata"],
                               nodata=0, resampling=Resampling.nearest) as vrt:
                    raw = vrt.read(1, masked=True)
            arrays[band] = raw.filled(0) if band == "scl" else reflectance(raw, meta["scale"], meta["offset"], meta["nodata"])
    rows, index = scene_rows(item, arrays["red"], arrays["nir"], arrays["scl"], grid, cfg)
    return rows, index, metadata


def ingest(cfg, grid, catalog, max_items=None):
    items = search_items(cfg, max_items)
    if not items:
        raise ValueError("No STAC scenes matched the configured AOI/dates/cloud limit.")
    stats = {"discovered": len(items), "processed": 0, "cached": 0, "raster_retries": 0, "failed": []}
    active_ids = []
    for number, item in enumerate(items, 1):
        ident = item["id"]
        fingerprint = source_hash(item)
        if catalog.current(ident, fingerprint):
            stats["cached"] += 1
            active_ids.append(ident)
            LOG.info("[%d/%d] cached %s", number, len(items), ident)
            continue
        try:
            modes = COG_ENDPOINT_MODES[:cfg["stac"].get("raster_attempts", 4)]
            last_error = None
            for attempt, endpoint_mode in enumerate(modes):
                try:
                    rows, index, metadata = load_scene(item, grid, cfg, endpoint_mode)
                    break
                except Exception as exc:
                    last_error = exc
                    if attempt + 1 >= len(modes) or not _transient_raster_error(exc):
                        raise
                    stats["raster_retries"] += 1
                    delay = cfg["stac"].get("retry_backoff_seconds", 0.5) * (2 ** attempt)
                    LOG.warning("%s raster read failed via %s (%s); retrying via %s in %.1fs",
                                ident, endpoint_mode, exc, modes[attempt + 1], delay)
                    if delay:
                        time.sleep(delay)
            else:
                raise last_error
            path = catalog.root / "rasters" / (digest(ident)[:24] + ".tif")
            write_ndvi(path, index, grid)
            catalog.commit_scene(item, fingerprint, {"assets": metadata, "scl_keep": cfg["quality"]["scl_keep"],
                                   "crs": grid.crs, "resolution_m": cfg["aoi"]["resolution_m"],
                                   "cache_namespace": catalog.root.name, "endpoint_mode": endpoint_mode,
                                   "transport_attempts": attempt + 1}, cfg["aoi"]["bbox"], path, rows)
            active_ids.append(ident)
            stats["processed"] += 1
            LOG.info("[%d/%d] processed %s; %d cells with pixels", number, len(items), ident, int((rows.valid_px > 0).sum()))
        except Exception as exc:
            LOG.error("%s failed: %s", ident, exc)
            catalog.fail(ident, exc)
            stats["failed"].append({"id": ident, "error": str(exc)})
    catalog.export_stac(cfg)
    return catalog.features(active_ids), stats, items
