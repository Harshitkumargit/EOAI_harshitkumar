"""Configuration validation and cache identity."""
from datetime import date
import json
from pathlib import Path

from .util import digest, file_hash


def validate(cfg):
    if cfg["model"].get("candidate_pool", "stable") not in ("stable", "research"):
        raise ValueError("model.candidate_pool must be stable or research.")
    if cfg["codes"] != ["R1", "S1", "D1", "T2"]:
        raise ValueError("Only R1/S1/D1/T2 is implemented. Different codes require a revised adapter/model.")
    a = cfg["aoi"]
    x0, y0, x1, y1 = a["bbox"]
    if not (73 <= x0 < x1 <= 78 and 28 <= y0 < y1 <= 33):
        raise ValueError("Use a valid small Punjab bbox in longitude/latitude order.")
    if a["crs"] != "EPSG:32643":
        raise ValueError("This project uses UTM 43N (EPSG:32643).")
    if not (10 <= a["resolution_m"] <= 1000 and a["cell_size_m"] >= a["resolution_m"]):
        raise ValueError("Invalid raster resolution or cell size.")
    if a["cell_size_m"] % a["resolution_m"]:
        raise ValueError("cell_size_m must be an integer multiple of resolution_m.")
    if (x1 - x0) > 1 or (y1 - y0) > 1:
        raise ValueError("Keep this laptop prototype AOI below one degree per side.")
    t = {k: date.fromisoformat(v) for k, v in cfg["time"].items()}
    s = {k: date.fromisoformat(v) for k, v in cfg["split"].items()}
    if not t["start"] < t["end"]:
        raise ValueError("time.start must precede time.end.")
    if not (t["start"] <= s["train_start"] <= s["train_end"] < s["test_start"] <= s["test_end"] <= t["end"]):
        raise ValueError("Train/test dates must be ordered, disjoint and inside the requested data window.")
    if any(v.weekday() != 0 for v in s.values()):
        raise ValueError("Split boundaries denote Monday target-week starts.")
    q = cfg["quality"]
    if not 0 < q["min_valid_fraction"] <= 1 or not 0 <= q["max_forward_fill_weeks"] <= 2:
        raise ValueError("Invalid coverage threshold or causal fill limit.")
    if not q["scl_keep"] or not set(q["scl_keep"]).issubset({4, 5, 6, 7}):
        raise ValueError("SCL keep must be a nonempty subset of 4,5,6,7.")
    if q["denominator_epsilon"] <= 0:
        raise ValueError("denominator_epsilon must be positive.")
    if cfg["model"]["lags"] != [0, 1, 2, 3]:
        raise ValueError("This feature contract requires lags [0,1,2,3].")
    for key in ("max_iter", "max_leaf_nodes", "min_samples_leaf", "threads", "min_train_rows", "min_train_weeks", "min_test_weeks"):
        if cfg["model"][key] < 1:
            raise ValueError(f"model.{key} must be positive.")
    if not 0 < cfg["model"]["learning_rate"] <= 1 or cfg["model"]["l2_regularization"] < 0:
        raise ValueError("Invalid learning rate or regularization.")
    e = cfg["evaluation"]
    if e["top_n"] < 1 or e["bootstrap_replicates"] < 1 or e["bootstrap_block_weeks"] < 1:
        raise ValueError("Invalid evaluation counts.")
    stac = cfg["stac"]
    if stac["url"].rstrip("/") != "https://earth-search.aws.element84.com/v1" or stac["collection"] != "sentinel-2-l2a":
        raise ValueError("The implemented scaling adapter supports Earth Search v1 sentinel-2-l2a only.")
    if not 0 <= stac["max_cloud"] <= 100 or stac["attempts"] < 1 or stac["timeout_seconds"] < 1:
        raise ValueError("Invalid STAC cloud/retry settings.")
    if not 1 <= stac.get("raster_attempts", 4) <= 4 or stac.get("retry_backoff_seconds", 0.5) < 0:
        raise ValueError("Raster attempts must be 1-4 and retry backoff must be nonnegative.")
    return cfg


def load_config(path):
    return validate(json.loads(Path(path).read_text(encoding="utf-8-sig")))


def processing_hash(cfg):
    # Dates and modelling thresholds do not change saved per-scene measurements.
    modules = ("grid.py", "preprocess.py", "ingest.py", "catalogue.py")
    source = {n: file_hash(Path(__file__).with_name(n)) for n in modules}
    # Exact reviewed transport-only revision: pixel processing is unchanged.
    # Only this byte-for-byte revision aliases the legacy identity; future edits invalidate it.
    if source["ingest.py"] == "fa12171efaed4d499898dee514b09fbc0b220e229ba06fa2762aa91ad015d808":
        source["ingest.py"] = "55721f41462ac6394a57880714477f1d09eb1f285a1586450b7d90ae6545cc09"
    return digest({"version": 1, "aoi": cfg["aoi"], "scl": cfg["quality"]["scl_keep"],
                   "epsilon": cfg["quality"]["denominator_epsilon"],
                   "collection": cfg["stac"]["collection"], "source": source})[:16]
