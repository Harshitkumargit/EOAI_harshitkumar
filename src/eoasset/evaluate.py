"""Paired baselines, coverage-aware ranking, and temporal-block uncertainty."""
import numpy as np
import pandas as pd


def errors(frame, method):
    e = frame[method].to_numpy() - frame.y.to_numpy()
    return {"n": len(frame), "mae": float(np.abs(e).mean()) if len(e) else None,
            "rmse": float(np.sqrt(np.mean(e ** 2))) if len(e) else None}


def skill(model_mae, baseline_mae):
    if model_mae is None or baseline_mae is None or baseline_mae <= 1e-12:
        return None
    return 1.0 - model_mae / baseline_mae


def ranking(frame, method, n):
    """Compare lowest-N lists only on observed, shortlist-eligible paired rows.

    At least 2N rows avoids automatic perfect overlap when nearly all rows are
    selected. This measures overlap on available truth, not every cell on the map.
    """
    scores = []
    for _, g in frame[frame.history_observed].groupby("target_week"):
        if len(g) < 2 * n:
            continue
        actual = set(g.sort_values(["y", "block_id"]).head(n).block_id)
        predicted = set(g.sort_values([method, "block_id"]).head(n).block_id)
        scores.append(len(actual & predicted) / n)
    return {"mean_overlap": float(np.mean(scores)) if scores else None, "n_weeks": len(scores), "top_n": n}


def temporal_bootstrap(frame, repeats, block_weeks, seed):
    """Resample contiguous calendar weeks with all cells kept together.

    Missing weeks contribute zero error sums. Both methods use the same sampled
    rows, so their count cancels in the MAE skill ratio. The resulting interval
    describes aggregate relative skill; it is not an interval for a cell forecast.
    """
    if frame.target_week.nunique() < 2 * block_weeks:
        return None
    d = frame.assign(model_error=np.abs(frame.y - frame.model), base_error=np.abs(frame.y - frame.persist))
    sums = d.groupby("target_week")[["model_error", "base_error"]].sum()
    calendar = pd.date_range(sums.index.min(), sums.index.max(), freq="W-MON")
    a = sums.reindex(calendar, fill_value=0).to_numpy()
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(repeats):
        starts = rng.integers(0, len(a) - block_weeks + 1, size=int(np.ceil(len(a) / block_weeks)))
        sample = np.concatenate([a[s:s + block_weeks] for s in starts])[:len(a)]
        model_sum, base_sum = sample.sum(axis=0)
        if base_sum > 1e-12:
            values.append(1.0 - model_sum / base_sum)
    return list(map(float, np.percentile(values, [2.5, 97.5]))) if values else None


def evaluate(test, cfg, available_rows):
    if test.empty or not test.y_observed.all():
        raise ValueError("Evaluation requires observed held-out targets.")
    pair = test.dropna(subset=["y", "model", "persist"])
    main = {method: errors(pair, method) for method in ("model", "persist")}
    common = pair.dropna(subset=["seasonal"])
    e = cfg["evaluation"]
    return {"n_test_rows": len(pair), "n_test_weeks": int(pair.target_week.nunique()),
            "n_test_cells": int(pair.block_id.nunique()), "requested_cell_weeks": int(available_rows),
            "evaluable_fraction": len(pair) / available_rows if available_rows else None,
            "primary": main,
            "skill_vs_persistence": skill(main["model"]["mae"], main["persist"]["mae"]),
            "skill_ci95": temporal_bootstrap(pair, e["bootstrap_replicates"], e["bootstrap_block_weeks"], cfg["model"]["seed"]),
            "bootstrap": {"replicates": e["bootstrap_replicates"], "block_weeks": e["bootstrap_block_weeks"],
                          "unit": "contiguous calendar weeks, all cells together", "interpretation": "descriptive holdout stability, not a per-cell prediction interval"},
            "ranking": {m: ranking(pair, m, e["top_n"]) for m in ("model", "persist")},
            "seasonal_common_sample": {"n": len(common), "methods": {m: errors(common, m) for m in ("model", "persist", "seasonal")},
                                       "ranking": {m: ranking(common, m, e["top_n"]) for m in ("model", "persist", "seasonal")}},
            "truth": "later observed weekly satellite NDVI; no field stress labels",
            "test_start": pair.target_week.min().date().isoformat(), "test_end": pair.target_week.max().date().isoformat()}
