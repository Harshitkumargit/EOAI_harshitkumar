"""Calendar-aligned, past-only forecasting features."""
import numpy as np
import pandas as pd

FEATURES = ["lag0", "lag1", "lag2", "lag3", "delta1", "roll4", "sin_year", "cos_year", "history_count", "valid_fraction", "n_days"]


def complete_weeks(cfg):
    start, end = (pd.Timestamp(cfg["time"][k]) for k in ("start", "end"))
    first = start + pd.Timedelta(days=(-start.weekday()) % 7)
    last_sunday = end - pd.Timedelta(days=(end.weekday() + 1) % 7)
    last = last_sunday - pd.Timedelta(days=6)
    if first > last:
        raise ValueError("The requested window contains no complete Monday-Sunday week.")
    return pd.date_range(first, last, freq="W-MON")


def weekly_table(scene, block_ids, cfg):
    """Keep every cell/week in the calendar, including weeks with no observation.

    Deduplicate by best daily coverage before the weekly median. The forward-filled
    ndvi column is for inputs only; raw_ndvi remains the unmodified target source.
    """
    weeks = complete_weeks(cfg)
    skeleton = pd.MultiIndex.from_product([block_ids, weeks], names=["block_id", "week"])
    d = scene.copy()
    d["day"] = pd.to_datetime(d["date"], utc=True).dt.tz_convert(None).dt.normalize()
    d = d[d["day"].between(weeks.min(), weeks.max() + pd.Timedelta(days=6))]
    d = d[(d.valid_fraction >= cfg["quality"]["min_valid_fraction"]) & np.isfinite(d.ndvi_mean)]
    # Highest clear fraction wins overlapping tiles/reprocessing on one date.
    d = d.sort_values(["block_id", "day", "valid_fraction", "item_id"], ascending=[True, True, False, True])
    d = d.drop_duplicates(["block_id", "day"], keep="first")
    d["week"] = d.day - pd.to_timedelta(d.day.dt.dayofweek, unit="D")
    agg = d.groupby(["block_id", "week"]).agg(raw_ndvi=("ndvi_mean", "median"),
               valid_fraction=("valid_fraction", "min"), n_days=("item_id", "count"))
    full = agg.reindex(skeleton).reset_index()
    full["observed"] = full.raw_ndvi.notna()
    full["valid_fraction"] = full.valid_fraction.fillna(0.0)
    full["n_days"] = full.n_days.fillna(0).astype(int)
    limit = cfg["quality"]["max_forward_fill_weeks"]
    full["ndvi"] = full.groupby("block_id").raw_ndvi.ffill(limit=limit) if limit else full.raw_ndvi
    full["filled"] = ~full.observed & full.ndvi.notna()
    return full


def supervised(weekly):
    """Build one-week-ahead labels and four past lags within each cell.

    A missing older lag need not discard an observed origin/target pair. The
    stricter history_observed flag controls action shortlists, not metric coverage.
    """
    d = weekly.sort_values(["block_id", "week"]).copy()
    g = d.groupby("block_id", sort=False)
    for lag in range(4):
        d[f"lag{lag}"] = g.ndvi.shift(lag)
    d["delta1"] = d.lag0 - d.lag1
    d["roll4"] = d[[f"lag{i}" for i in range(4)]].mean(axis=1, skipna=False)
    # Day-of-year uses a smooth 365.2425-day cycle rather than an artificial week 53 jump.
    angle = 2 * np.pi * d.week.dt.dayofyear.to_numpy() / 365.2425
    d["sin_year"], d["cos_year"] = np.sin(angle), np.cos(angle)
    d["target_week"] = d.week + pd.Timedelta(days=7)
    d["y"] = g.raw_ndvi.shift(-1)
    d["y_observed"] = g["observed"].shift(-1).eq(True)
    d["persist"] = d.raw_ndvi
    d["seasonal"] = g.raw_ndvi.shift(51)  # (origin + 1) - 52 = origin - 51
    d["history_observed"] = True
    d["history_count"] = 0
    for lag in range(4):
        d["history_observed"] &= g["observed"].shift(lag).eq(True)
        d["history_count"] += g["observed"].shift(lag).eq(True).astype(int)
    # Missing historical inputs are supported by HGB; origin and truth remain observed.
    d["feature_ready"] = d.observed & np.isfinite(d.lag0)
    return d.reset_index(drop=True)
