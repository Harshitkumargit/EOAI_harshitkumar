"""Artificial scene summaries for tests; never evidence of satellite performance."""
import numpy as np
import pandas as pd


def make_scenes(cfg, grid):
    rng = np.random.default_rng(cfg["model"]["seed"])
    dates = pd.date_range(cfg["time"]["start"], cfg["time"]["end"], freq="5D")
    rows = []
    for cell, (bid, total) in enumerate(zip(grid.ids, grid.totals)):
        phase = rng.uniform(-0.20, 0.20)
        baseline = rng.uniform(0.28, 0.40)
        for j, day in enumerate(dates):
            value = baseline + 0.22 * np.sin(2 * np.pi * (day.dayofyear - 10) / 365.2425 + phase)
            value += rng.normal(0, 0.015)
            if cell % 13 == 0 and j > len(dates) - 12:
                value -= 0.13
            fraction = float(rng.uniform(0.50, 0.95))
            if rng.random() < 0.035:
                fraction = 0.1
            count = int(total * fraction)
            rows.append({"item_id": f"SYNTHETIC_{day:%Y%m%d}", "date": day.isoformat(), "block_id": bid,
                         "ndvi_mean": float(np.clip(value, 0.01, 0.95)), "valid_px": count,
                         "total_px": int(total), "valid_fraction": count / total, "cloud_cover": 100 * (1 - fraction)})
    return pd.DataFrame(rows)
