"""Transactional catalogue and feature store; JSON export is derived metadata."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3

import pandas as pd

from .grid import bbox_geometry
from .util import clean, file_hash, utc_now, write_json

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS scenes (
 id TEXT PRIMARY KEY, acquired TEXT NOT NULL, source_hash TEXT NOT NULL,
 source_json TEXT NOT NULL, processing_json TEXT NOT NULL,
 minx REAL, miny REAL, maxx REAL, maxy REAL,
 raster TEXT NOT NULL, raster_hash TEXT NOT NULL, row_count INTEGER NOT NULL,
 completed TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS features (
 item_id TEXT NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
 block_id TEXT NOT NULL, date TEXT NOT NULL, ndvi_mean REAL,
 valid_px INTEGER NOT NULL, total_px INTEGER NOT NULL,
 valid_fraction REAL NOT NULL, cloud_cover REAL,
 PRIMARY KEY(item_id, block_id)
);
CREATE INDEX IF NOT EXISTS idx_scenes_date ON scenes(acquired);
CREATE INDEX IF NOT EXISTS idx_features_date ON features(date);
CREATE TABLE IF NOT EXISTS failures (id TEXT PRIMARY KEY, error TEXT NOT NULL, attempted TEXT NOT NULL);
"""


@contextmanager
def cache_lock(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    lock = root / "writer.lock"
    try:
        stream = lock.open("x", encoding="utf-8")
    except FileExistsError as exc:
        raise RuntimeError(f"Cache writer lock exists: {lock}. Check for a running pipeline before removing a stale lock.") from exc
    try:
        import os
        stream.write(f"pid={os.getpid()} created={utc_now()}\n")
        stream.close()
        yield
    finally:
        stream.close()
        lock.unlink(missing_ok=True)


class Catalogue:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "catalogue.sqlite")
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.db.close()

    def current(self, item_id, source_hash):
        row = self.db.execute("SELECT * FROM scenes WHERE id=?", (item_id,)).fetchone()
        if row is None or row["source_hash"] != source_hash:
            return False
        raster = self.root / row["raster"]
        count = self.db.execute("SELECT count(*) FROM features WHERE item_id=?", (item_id,)).fetchone()[0]
        return count == row["row_count"] and raster.is_file() and file_hash(raster) == row["raster_hash"]

    def commit_scene(self, item, source_hash, processing, bbox, raster, rows):
        raster = Path(raster)
        if not raster.is_file() or rows.empty or rows["block_id"].duplicated().any():
            raise ValueError("Commit requires a completed raster and one feature row per cell.")
        source = clean(item)
        values = (item["id"], item["properties"]["datetime"], source_hash, json.dumps(source),
                  json.dumps(clean(processing)), *bbox, str(raster.relative_to(self.root)),
                  file_hash(raster), len(rows), utc_now())
        records = clean(rows[["item_id", "block_id", "date", "ndvi_mean", "valid_px", "total_px",
                              "valid_fraction", "cloud_cover"]].to_dict("records"))
        with self.db:
            self.db.execute("DELETE FROM scenes WHERE id=?", (item["id"],))
            self.db.execute("INSERT INTO scenes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", values)
            self.db.executemany("INSERT INTO features VALUES (:item_id,:block_id,:date,:ndvi_mean,:valid_px,:total_px,:valid_fraction,:cloud_cover)", records)
            self.db.execute("DELETE FROM failures WHERE id=?", (item["id"],))

    def fail(self, item_id, error):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO failures VALUES (?,?,?)", (item_id, str(error), utc_now()))

    def failures(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM failures ORDER BY id")]

    def query(self, start, end, bbox=None):
        sql = "SELECT * FROM scenes WHERE substr(acquired,1,10)>=? AND substr(acquired,1,10)<=?"
        params = [start, end]
        if bbox:
            sql += " AND maxx>=? AND maxy>=? AND minx<=? AND miny<=?"
            params.extend(bbox)
        return [dict(r) for r in self.db.execute(sql + " ORDER BY acquired,id", params)]

    def features(self, ids):
        if not ids:
            return pd.DataFrame(columns=["item_id", "block_id", "date", "ndvi_mean", "valid_px", "total_px", "valid_fraction", "cloud_cover"])
        # Avoid SQLite's variable-count limit on a longer historical run.
        frames = []
        ids = sorted(set(ids))
        for first in range(0, len(ids), 400):
            chunk = ids[first:first + 400]
            sql = "SELECT * FROM features WHERE item_id IN (" + ",".join("?" for _ in chunk) + ")"
            frames.append(pd.read_sql_query(sql, self.db, params=chunk))
        return pd.concat(frames, ignore_index=True).sort_values(["date", "block_id", "item_id"])

    def export_stac(self, cfg):
        root = self.root / "stac"
        links = [{"rel": "self", "href": "catalog.json", "type": "application/json"}]
        for row in self.query("0001-01-01", "9999-12-31"):
            name = row["raster_hash"][:12] + "-" + Path(row["raster"]).stem + ".json"
            bbox = [row[k] for k in ("minx", "miny", "maxx", "maxy")]
            source = json.loads(row["source_json"])
            item = {"type": "Feature", "stac_version": "1.0.0", "id": row["id"],
                    "geometry": bbox_geometry(bbox), "bbox": bbox,
                    "properties": {"datetime": row["acquired"], "eoasset:processing": json.loads(row["processing_json"]),
                                   "eoasset:source_collection": source.get("collection", cfg["stac"]["collection"]),
                                   "eoasset:raster_sha256": row["raster_hash"], "eoasset:units": "dimensionless NDVI"},
                    "links": [{"rel": "root", "href": "../catalog.json", "type": "application/json"},
                              {"rel": "parent", "href": "../catalog.json", "type": "application/json"}],
                    "assets": {"ndvi": {"href": "../../" + Path(row["raster"]).as_posix(), "type": "image/tiff; application=geotiff", "roles": ["data"]}}}
            write_json(root / "items" / name, item)
            links.append({"rel": "item", "href": "items/" + name, "type": "application/geo+json"})
        write_json(root / "catalog.json", {"type": "Catalog", "stac_version": "1.0.0", "id": "punjab-vegetation-watch",
                   "description": "Derived SCL-masked Sentinel-2 NDVI. Contains modified Copernicus Sentinel data; source attribution retained in SQLite.", "links": links})
