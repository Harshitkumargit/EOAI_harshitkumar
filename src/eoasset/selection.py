"""Training-only rolling-origin selection with an explicit persistence candidate."""
import os
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
from .features import FEATURES

# Fixed before running the extended training-season experiment. No test-score search.
CANDIDATES = ("persistence", "direct", "residual", "absolute_direct",
              "absolute_residual", "shrink_residual", "ridge_10", "ridge_100",
              "median_25", "median_50", "trend_25", "trend_50")

def relative_inputs(x):
    """Level-relative lags with explicit missingness; no fitted imputation or future data."""
    x = np.asarray(x, dtype=float)
    relative = x[:, 1:4] - x[:, :1]
    return np.column_stack((np.nan_to_num(relative), np.isnan(relative).astype(float),
                            x[:, 0], x[:, 6:]))

class ForecastModel:
    """Serializable predictor; kind and features travel with the saved model."""
    def __init__(self, kind, estimator=None):
        self.kind, self.estimator = kind, estimator
        self.feature_names = list(FEATURES)

    def predict(self, x):
        x = np.asarray(x)
        base = x[:, 0]
        if self.kind == "persistence":
            return base
        if self.kind.startswith("median_"):
            weight = int(self.kind.split("_")[1]) / 100
            return base + weight * (np.nanmedian(x[:, :4], axis=1) - base)
        if self.kind.startswith("trend_"):
            weight = int(self.kind.split("_")[1]) / 100
            # Conservative one-step extrapolation, not Holt's fitted damped trend.
            change = np.nan_to_num(base - x[:, 1])
            return base + weight * change
        if self.kind.startswith("ridge_"):
            return base + self.estimator.predict(relative_inputs(x))
        pred = self.estimator.predict(x)
        if self.kind == "shrink_residual":
            return base + .25 * pred
        return pred + base if self.kind in ("residual", "absolute_residual") else pred

def fit_candidate(frame, cfg, kind):
    """Fit only the supplied fold; residual models learn y minus current NDVI.

    Ridge scaling stays inside its fitted pipeline. HGB early stopping is disabled
    because a random internal split would not enforce this temporal experiment.
    """
    if kind not in CANDIDATES:
        raise ValueError(f"Unknown candidate: {kind}")
    if kind == "persistence" or kind.startswith(("median_", "trend_")):
        return ForecastModel(kind)
    c = cfg["model"]
    os.environ.setdefault("LOKY_MAX_CPU_COUNT", str(c["threads"]))
    if kind.startswith("ridge_"):
        estimator = make_pipeline(StandardScaler(), Ridge(alpha=float(kind.split("_")[1])))
        with threadpool_limits(limits=c["threads"]):
            estimator.fit(relative_inputs(frame[FEATURES].to_numpy()), (frame.y-frame.lag0).to_numpy())
        return ForecastModel(kind, estimator)
    estimator = HistGradientBoostingRegressor(
        max_iter=c["max_iter"], learning_rate=c["learning_rate"],
        max_leaf_nodes=c["max_leaf_nodes"], min_samples_leaf=c["min_samples_leaf"],
        l2_regularization=c["l2_regularization"], random_state=c["seed"],
        early_stopping=False,
        loss="absolute_error" if kind.startswith("absolute_") or kind == "shrink_residual" else "squared_error")
    target = frame.y - frame.lag0 if kind in ("residual", "absolute_residual", "shrink_residual") else frame.y
    with threadpool_limits(limits=c["threads"]):
        estimator.fit(frame[FEATURES].to_numpy(), target.to_numpy())
    return ForecastModel(kind, estimator)

def select_candidate(train, cfg):
    """Only receives earlier-season training data. All cells stay together by week."""
    weeks = sorted(train.target_week.unique())
    folds = []
    # Three non-overlapping validation windows of four observed target weeks.
    for start in (len(weeks)-12, len(weeks)-8, len(weeks)-4):
        if start < 4:
            continue
        validation = train[train.target_week.isin(weeks[start:start+4])]
        cutoff = pd.Timestamp(weeks[start]) - pd.Timedelta(days=7)
        fitting = train[train.target_week < cutoff]
        if len(fitting) < cfg["model"]["min_train_rows"] or fitting.target_week.nunique() < 4:
            continue
        folds.append((fitting, validation))
    pool = cfg["model"].get("candidate_pool", "stable")
    if pool not in ("stable", "research"):
        raise ValueError("candidate_pool must be stable or research")
    kinds = CANDIDATES if pool == "research" else CANDIDATES[:3]
    scores, details = {}, []
    for kind in kinds:
        weekly_errors = []
        for fitting, validation in folds:
            candidate = fit_candidate(fitting, cfg, kind)
            with threadpool_limits(limits=cfg["model"]["threads"]):
                pred = np.clip(candidate.predict(validation[FEATURES].to_numpy()), -1, 1)
            errors = validation.assign(error=np.abs(pred-validation.y.to_numpy()))
            weekly_errors.extend(errors.groupby("target_week").error.mean().tolist())
            details.append({"candidate":kind,"train_end":str(fitting.target_week.max().date()),
                            "validation_start":str(validation.target_week.min().date()),
                            "validation_end":str(validation.target_week.max().date()),
                            "rows":len(validation), "train_rows":len(fitting),
                            "weekly_mae": {str(w.date()):float(v) for w,v in errors.groupby("target_week").error.mean().items()},
                            "mae":float(errors.error.mean())})
        scores[kind] = float(np.mean(weekly_errors)) if weekly_errors else None
    # Stable tie-break prefers persistence. No usable folds means persistence.
    chosen = min(kinds, key=lambda k: scores[k] if scores[k] is not None else float("inf"))
    fold_scores = {k:[float(np.mean(list(d["weekly_mae"].values())))
                      for d in details if d["candidate"] == k] for k in kinds}
    # Sensitivity diagnostic only; never consults later-season labels.
    omissions = []
    if len(folds) > 1:
        for omitted in range(len(folds)):
            winner = min(kinds, key=lambda k: np.mean([v for i,v in enumerate(fold_scores[k]) if i != omitted]))
            omissions.append({"omitted_fold":omitted, "selected":winner})
    return chosen, {"selected":chosen,"objective":"mean weekly MAE",
                    "candidate_scores":scores,"folds":details,
                    "candidate_order":list(kinds),
                    "candidate_pool":pool,
                    "fold_mean_weekly_mae":fold_scores,"leave_one_fold_out":omissions,
                    "selection_caution":"Small correlated sample; validation winner is not proof of generalization.",
                    "scope":"earlier training season only; one calendar-week gap",
                    "evaluation_status":"development replay: later-season results were inspected before this revision"}

