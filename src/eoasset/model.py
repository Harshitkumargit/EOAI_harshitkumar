"""Chronological model assessment, then an independently fitted replay forecast."""
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from .evaluate import evaluate
from .features import FEATURES
from .selection import fit_candidate, select_candidate


def predict(model, frame, cfg):
    with threadpool_limits(limits=cfg["model"]["threads"]):
        return np.clip(model.predict(frame[FEATURES].to_numpy()), -1.0, 1.0)


def run_model(table, cfg):
    """Select on the earlier season, score the later season, then fit for publication.

    The assessment model never sees later labels during fitting. This is still a
    development replay because earlier project revisions inspected those outcomes.
    The final model may use completed later history; its predictions never replace
    assessment predictions in metrics. Forecast ranks require four observed weeks.
    """
    s, c = cfg["split"], cfg["model"]
    labelled = table[table.feature_ready & table.y_observed & table.y.notna()].copy()
    train = labelled[labelled.target_week.between(s["train_start"], s["train_end"])].copy()
    test = labelled[labelled.target_week.between(s["test_start"], s["test_end"])].copy()
    if len(train) < c["min_train_rows"] or train.target_week.nunique() < c["min_train_weeks"]:
        raise ValueError(f"Insufficient training data: {len(train)} rows, {train.target_week.nunique()} weeks. Run full ingestion, inspect coverage, or use --ingest-only for a trial.")
    if test.target_week.nunique() < c["min_test_weeks"]:
        raise ValueError(f"Insufficient held-out data: {test.target_week.nunique()} weeks. Inspect scene coverage and split dates.")
    if train.target_week.max() + pd.Timedelta(days=6) >= test.target_week.min():
        raise ValueError("Training target-week observations overlap the test period.")
    chosen, selection = select_candidate(train, cfg)
    assessment = fit_candidate(train, cfg, chosen)
    test["model"] = predict(assessment, test, cfg)
    available = table[table.target_week.between(s["test_start"], s["test_end"])]
    metrics = evaluate(test, cfg, len(available))
    metrics["selection"] = selection
    metrics["coverage_diagnostics"] = {
        "requested": len(available),
        "observed_origin": int(available.observed.sum()),
        "observed_target": int(available.y_observed.sum()),
        "observed_origin_and_target": int((available.observed & available.y_observed).sum()),
        "complete_observed_history_and_target": int((available.history_observed & available.y_observed).sum()),
        "scored": len(test),
    }
    metrics["by_week"] = [{"target_week": str(w.date()), "n": len(g),
        "model_mae": float(abs(g.model-g.y).mean()), "persistence_mae": float(abs(g.persist-g.y).mean())}
        for w, g in test.groupby("target_week")]
    metrics["mean_weekly_mae"] = {
        "model": float(np.mean([r["model_mae"] for r in metrics["by_week"]])),
        "persistence": float(np.mean([r["persistence_mae"] for r in metrics["by_week"]]))}
    metrics["training"] = {"n": len(train), "n_weeks": int(train.target_week.nunique()),
                           "target_start": train.target_week.min().date().isoformat(), "target_end": train.target_week.max().date().isoformat()}
    # All labels here end by the origin Sunday, not the future target Sunday.
    origin = table.week.max()
    refit_rows = labelled[labelled.target_week <= origin]
    final = fit_candidate(refit_rows, cfg, chosen)
    latest = table[table.week == origin].copy()
    latest["prediction"] = np.nan
    ready = latest.feature_ready
    if ready.any():
        latest.loc[ready, "prediction"] = predict(final, latest[ready], cfg)
    latest["shortlist_eligible"] = ready & latest.history_observed
    latest["status"] = np.select([~latest.observed, ~ready, ~latest.history_observed],
                                 ["no_current_observation", "insufficient_history", "incomplete_history_withheld"], default="eligible")
    latest["change"] = latest.prediction - latest.raw_ndvi
    latest["rank"] = np.nan
    ordered = latest[latest.shortlist_eligible].sort_values(["prediction", "block_id"]).index
    latest.loc[ordered, "rank"] = np.arange(1, len(ordered) + 1)
    latest["shortlisted"] = latest["rank"].le(cfg["evaluation"]["top_n"])
    forecast = latest[["block_id", "week", "target_week", "raw_ndvi", "prediction", "change", "valid_fraction", "status", "rank", "shortlisted", "shortlist_eligible"]].rename(columns={"week": "origin_week", "raw_ndvi": "observed_ndvi"})
    metrics["refit"] = {"n": len(refit_rows), "n_weeks": int(refit_rows.target_week.nunique()),
                        "note": "Separate final fit on available historical observed targets; not used in held-out scores."}
    return metrics, test, forecast, assessment, final
