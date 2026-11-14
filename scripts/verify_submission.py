"""Verify the compact package without downloads or the omitted raster cache.

Recompute errors from saved predictions, compare embedded dashboard data with the
standalone JSON files, and check every packaged hash. This checks consistency of
saved evidence; it cannot validate the physical calibration of satellite pixels.
Run from any directory: python scripts/verify_submission.py
"""
import hashlib
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    def invalid(value):
        raise ValueError(f"Nonstandard JSON number {value} in {path}")
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=invalid)


def check_score(frame, column, expected):
    error = frame[column].to_numpy() - frame.y.to_numpy()
    require(len(frame) == expected["n"], f"Count differs for {column}")
    require(np.isclose(np.abs(error).mean(), expected["mae"], atol=1e-12), f"MAE differs: {column}")
    require(np.isclose(np.sqrt(np.mean(error ** 2)), expected["rmse"], atol=1e-12), f"RMSE differs: {column}")


def main():
    metrics = read_json(ROOT / "metrics.json")
    predictions = pd.read_csv(ROOT / "test_predictions.csv")
    require(not predictions.duplicated(["block_id", "target_week"]).any(), "Duplicate prediction keys")
    require(predictions.y_observed.all(), "Scored target was not observed")
    for method in ("model", "persist"):
        check_score(predictions, method, metrics["primary"][method])
    common = predictions.dropna(subset=["seasonal"])
    for method, score in metrics["seasonal_common_sample"]["methods"].items():
        check_score(common, method, score)
    require(len(predictions) == metrics["n_test_rows"], "Wrong prediction count")
    require(np.isclose(len(predictions) / metrics["requested_cell_weeks"], metrics["evaluable_fraction"]), "Wrong coverage")
    for method, score in metrics["ranking"].items():
        overlap = []
        for _, rows in predictions[predictions.history_observed].groupby("target_week"):
            n = score["top_n"]
            if len(rows) >= 2 * n:
                actual = set(rows.sort_values(["y", "block_id"]).head(n).block_id)
                predicted = set(rows.sort_values([method, "block_id"]).head(n).block_id)
                overlap.append(len(actual & predicted) / n)
        require(len(overlap) == score["n_weeks"], "Wrong ranking week count")
        require(np.isclose(np.mean(overlap), score["mean_overlap"]), "Wrong ranking overlap")

    html = (ROOT / "dashboard.html").read_text(encoding="utf-8")
    match = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S)
    require(match is not None, "Missing dashboard data")
    data = json.loads(match.group(1))
    for key, file in [("metrics", "metrics.json"), ("meta", "meta.json"), ("config", "config.json"), ("signals", "block_signals.geojson")]:
        require(data[key] == read_json(ROOT / file), f"Dashboard {key} differs from {file}")

    # The saved comparisons must match the actual predictions, on identical keys.
    for record, old_file, new_file in [
        ("revision_comparison.json", "original_predictions.csv", None),
        ("extended_research_comparison.json", None, "median_blend_predictions.csv"),
    ]:
        comparison = read_json(ROOT / "reports" / record)
        old = pd.read_csv(ROOT / "reports/evidence" / old_file) if old_file else predictions
        new = pd.read_csv(ROOT / "reports/evidence" / new_file) if new_file else predictions
        paired = old.merge(new, on=["block_id", "target_week"], suffixes=("_old", "_new"), validate="one_to_one")
        require(len(paired) == comparison["common_rows"], f"Comparison count differs: {record}")
        require(np.allclose(paired.y_old, paired.y_new), f"Targets differ: {record}")
        for label, col in [("original", "model_old"), ("revised", "model_new"), ("persistence", "persist_new")]:
            frame = pd.DataFrame({"y": paired.y_new, "prediction": paired[col]})
            check_score(frame, "prediction", {"n": len(frame), **comparison["same_sample"][label]})

    manifest = read_json(ROOT / "manifest.json")
    for name, entry in manifest["files"].items():
        file = ROOT / name
        require(file.is_file(), f"Missing packaged file: {name}")
        raw = file.read_bytes()
        require(len(raw) == entry["bytes"] and hashlib.sha256(raw).hexdigest() == entry["sha256"], f"Hash mismatch: {name}")
    for file in ROOT.rglob("*.md"):
        for link in re.findall(r'\[[^]]*\]\(([^)]+)\)', file.read_text(encoding="utf-8")):
            if not link.startswith(("http:", "https:", "mailto:", "#")):
                require((file.parent / link.split("#")[0]).exists(), f"Broken local link in {file}: {link}")
    for file in ROOT.rglob("*.json"):
        read_json(file)
    print("PASS: saved errors, coverage, rankings, experiment comparisons, dashboard data, local links, JSON, and package hashes")
    print("Scope: numerical/package consistency only; no new imagery or independent radiometric verification.")


if __name__ == "__main__":
    main()
