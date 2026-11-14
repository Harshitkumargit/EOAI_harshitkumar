"""Publish an immutable run directory and an atomic latest pointer."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time
import uuid

import joblib
import numpy as np

from .dashboard import render
from .features import FEATURES
from .util import atomic_text, clean, code_hash, environment, file_hash, utc_now, write_json


def records(frame):
    # pandas' JSON conversion correctly handles Timestamp, NaT and NaN together.
    return json.loads(frame.to_json(orient="records", date_format="iso"))


def radiometry_status(sources, mode):
    if mode == "synthetic":
        return {"status":"not_applicable", "conflicting_scene_ids":[]}
    conflicts = []
    for item in sources:
        if item.get("properties", {}).get("earthsearch:boa_offset_applied") is True:
            if any((item.get("assets", {}).get(band, {}).get("raster:bands") or [{}])[0].get("offset", 0) != 0 for band in ("red", "nir")):
                conflicts.append(item["id"])
    return {"status":"provisional_unverified", "conflicting_scene_ids":conflicts,
            "message":"Satellite radiometry has not been independently verified. Legacy provider offset metadata may be inconsistent; current NDVI metrics are provisional. Conflicting metadata is a review flag, not proof of erroneous pixels.",
            "source":"https://github.com/Element84/earth-search/issues/71"}


def figures(out, weekly, test, forecast, grid, mode):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection

    dest = out / "figures"
    dest.mkdir()
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    fig.suptitle("SYNTHETIC DEMO - not real performance" if mode == "synthetic" else "Historical satellite evaluation")
    axes[0].scatter(test.y, test.model, s=3, alpha=.25)
    axes[0].plot([-1, 1], [-1, 1], "k--", lw=1)
    axes[0].set(xlabel="Observed NDVI", ylabel="Predicted NDVI", title="Held-out predictions")
    trend = test.assign(model_error=abs(test.y - test.model), persist_error=abs(test.y - test.persist)).groupby("target_week")[["model_error", "persist_error"]].mean()
    axes[1].plot(trend.index, trend.model_error, label="Model")
    axes[1].plot(trend.index, trend.persist_error, label="Persistence")
    axes[1].legend()
    axes[1].set(ylabel="MAE (NDVI)", title="Error by target week")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(dest / "evaluation.png", dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 4))
    fig.suptitle("SYNTHETIC DEMO - artificial observations" if mode == "synthetic" else "Historical satellite observations")
    chosen = forecast.sort_values(["prediction", "block_id"]).head(3).block_id
    for bid in chosen:
        d = weekly[weekly.block_id == bid]
        ax.plot(d.week, d.raw_ndvi, label=bid)
    ax.legend()
    ax.set(ylabel="Observed NDVI", title="Observed weekly histories (gaps remain gaps)")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(dest / "histories.png", dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 7))
    fig.suptitle("SYNTHETIC DEMO - not an advisory" if mode == "synthetic" else "Historical replay - not a current advisory")
    pred = forecast.set_index("block_id")
    polygons, colors = [], []
    for cell in grid.cells:
        row = pred.loc[cell["properties"]["block_id"]]
        geom = cell["geometry"]
        parts = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for poly in parts:
            polygons.append(poly[0])
            colors.append(row.prediction if row.shortlist_eligible else np.nan)
    cmap = plt.get_cmap("RdYlGn").copy()
    cmap.set_bad("lightgrey")
    collection = PolyCollection(polygons, array=np.ma.masked_invalid(colors), cmap=cmap, edgecolors="white", linewidths=.2)
    collection.set_clim(0, .8)
    ax.add_collection(collection)
    ax.autoscale_view()
    lat = np.mean([xy[1] for poly in polygons for xy in poly])
    ax.set_aspect(1 / np.cos(np.deg2rad(lat)))
    ax.set(xlabel="Longitude", ylabel="Latitude", title="Forecast NDVI; grey = withheld")
    fig.colorbar(collection, ax=ax, label="NDVI")
    fig.tight_layout()
    fig.savefig(dest / "forecast_map.png", dpi=160)
    plt.close(fig)


def report_text(meta, cfg, metrics, worst):
    def f(v):
        return "unavailable" if v is None else f"{v:.4f}"
    p = metrics["primary"]
    note = "SYNTHETIC DEMO: these metrics are artificial and are not real performance evidence." if meta["data_mode"] == "synthetic" else "Historical satellite replay; no field-confirmed crop stress labels."
    rows = "\n".join(f"| {m} | {v['n']} | {f(v['mae'])} | {f(v['rmse'])} |" for m, v in p.items())
    # Describe the pool actually evaluated, rather than all implemented candidates.
    pool = ", ".join(metrics["selection"]["candidate_order"])
    return f"""# Punjab Vegetation Watch — run report

**Codes: R1 / S1 / D1 / T2. Self-selected with user authorization; not confirmed by the lab.**

{note}

Radiometry status: {meta.get('radiometry', {}).get('status', 'unverified')}. {meta.get('radiometry', {}).get('message', '')}

## User and decision
A district agriculture officer in the Ludhiana-Patiala belt needs a weekly shortlist of up to {cfg['evaluation']['top_n']} approximately 3 km cells to inspect. The signal is relative predicted NDVI, not a crop-stress diagnosis. Useful means outperforming persistence with adequate coverage; no improvement is assumed.

## Data and implementation
AOI {cfg['aoi']['bbox']}; Sentinel-2 L2A red/NIR/SCL from Earth Search v1. {meta['n_scenes']} scenes; observation cutoff {meta['observation_cutoff']}. Apply explicit radiometric metadata once, retain SCL {cfg['quality']['scl_keep']}, align to {cfg['aoi']['resolution_m']} m UTM 43N, and require {cfg['quality']['min_valid_fraction']:.0%} usable cell area. Select one best-coverage scene per cell/day, then take weekly medians. Missing targets remain missing. Lag-only forward-fill is causal and flagged.

SQLite transactions retain source metadata, checksums and scene/cell features. Repeated unchanged scenes are skipped; changed source metadata or corrupt rasters are retried. The manifest links inputs, code, config, versions and output hashes. The static HTML asset renders the saved result without a server.

## Method and evaluation
The selected predictor is {metrics['selection']['selected']}. Evaluated candidates: {pool}. Persistence carries the current observed NDVI forward; the stable pool compares it with direct and residual boosting. Additional robust-loss, ridge, median and trend candidates are available only in the research pool. All share the eleven-input contract, although persistence uses only current NDVI. Training target weeks: {cfg['split']['train_start']} to {cfg['split']['train_end']}; later evaluation: {cfg['split']['test_start']} to {cfg['split']['test_end']}. Same cells, later season. Features use only information through the origin Sunday. The separate final refit is not used for evaluation metrics.

Revision: missing historical lags are supported; history count, current usable fraction and observation-day count are additional inputs. Selection compares a fixed small candidate pool using earlier-season rolling validation; candidate definitions and fold sensitivity are recorded below. Selected predictor: {metrics.get('selection', {}).get('selected', 'legacy direct')}. Selection details: {json.dumps(clean(metrics.get('selection', {})))}.

This revised result is a development replay because the later-season results informed the audit. A fresh untouched season is needed for a new confirmatory claim. Coverage diagnostics: {json.dumps(clean(metrics.get('coverage_diagnostics', {})))}. Equal-week MAE: {json.dumps(clean(metrics.get('mean_weekly_mae', {})))}. Per-week errors are in metrics.json.

| Method | Rows | MAE | RMSE |
|---|---:|---:|---:|
{rows}

Skill versus persistence: {f(metrics['skill_vs_persistence'])}; 95% temporal-block interval: {metrics['skill_ci95']}. Coverage: {metrics['n_test_rows']}/{metrics['requested_cell_weeks']} cell-weeks; {metrics['n_test_weeks']} held-out weeks. Seasonal common sample: {metrics['seasonal_common_sample']['n']} rows (full metrics in metrics.json). Ranking results: {json.dumps(clean(metrics['ranking']))}.

The asset includes a geographic forecast map, cell histories, observed-vs-predicted scatter and worst-error examples. PNG figures are in figures/. Inspect large errors against source imagery; do not assume a physical cause from prediction error. Example cells: {', '.join(r['block_id'] for r in worst)}.

## Configuration question: why this sensor?
Sentinel-2 red/NIR surface reflectance measures vegetation greenness directly. SCL masking and usable-area thresholds address obvious clouds and shadows, but thin haze can remain. A 20 m grid is adequate for cell-level aggregates. NDVI can saturate and bare soil, mixed land cover and harvest affect its interpretation. This is not a crop-specific index without an external crop mask.

## Fitness for use: would the officer trust it today?
Use it only to guide exploratory inspection with local knowledge. No field validation, crop diagnosis or yield claims are supported. Production needs officer feedback, crop/official boundary data, more seasons, ground observations, publication-latency validation, drift monitoring and ingestion alerts. Historical availability is approximated by acquisition week; real publication delays are not simulated.

## Limitations and reproduction
Observation gaps select which targets can be scored. A four-week bootstrap retains all cells together but does not establish universal uncertainty. Relative ranking always chooses up to the visit budget even when every cell is healthy. Forecast origin {meta['origin_week']}; target {meta['target_week']}; a stale archive is not a current advisory. Partial ingestion: {meta['partial']}.

From the project root, run `py -3.10 run.py` (real data) or `py -3.10 run.py --offline` (demo). Run ID {meta['run_id']}; code {meta['code_hash']}. Elapsed pipeline time: {meta['elapsed_seconds']:.1f} s. See this run's manifest.json and the project-root README.md, docs/data_model_card.md and ai_assistant_log.md. Applicant review and independent source verification remain necessary before operational claims.
"""


def publish(root, cfg, grid, scene, weekly, metrics, test, forecast, models, mode, stats, sources, started, make_figures=True):
    root = Path(root)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    out = root / "runs" / run_id
    out.mkdir(parents=True, exist_ok=False)
    origin = weekly.week.max()
    meta = {"run_id": run_id, "data_mode": mode, "generated_at": utc_now(),
            "origin_week": origin.date().isoformat(), "target_week": (origin + timedelta(days=7)).date().isoformat(),
            "observation_cutoff": (origin + timedelta(days=6)).date().isoformat(),
            "last_scene_date": str(scene.date.max())[:10], "n_scenes": int(scene.item_id.nunique()),
            "partial": bool(stats.get("failed")), "code_hash": code_hash(), "elapsed_seconds": time.monotonic() - started}
    meta["radiometry"] = radiometry_status(sources, mode)
    metrics = {**metrics, "data_mode": mode, "radiometry_status":meta["radiometry"]["status"]}
    write_json(out / "radiometry_status.json", meta["radiometry"])
    lookup = {r["block_id"]: r for r in records(forecast)}
    cells = [{**c, "properties": {**c["properties"], **lookup[c["properties"]["block_id"]]}} for c in grid.cells]
    signals = {"type": "FeatureCollection", "features": cells}
    ranked_error = test.assign(abs_error=abs(test.y - test.model)).sort_values(["abs_error", "block_id"])
    worst = records(ranked_error.tail(5).iloc[::-1])
    payload = {"meta": meta, "config": cfg, "metrics": metrics, "signals": signals,
               "history": records(weekly), "worst": worst,
               "scatter": records(test.iloc[::max(1, len(test) // 1500)][["y", "model"]])}
    write_json(out / "metrics.json", metrics)
    write_json(out / "meta.json", meta)
    write_json(out / "block_signals.geojson", signals)
    write_json(out / "ingestion_status.json", stats)
    write_json(out / "error_examples.json", {"best": records(ranked_error.head(5)), "worst": worst})
    write_json(out / "source_items.json", sources)
    for name, frame in [("scene_features", scene), ("weekly", weekly), ("test_predictions", test), ("forecast", forecast)]:
        frame.to_csv(out / (name + ".csv"), index=False, date_format="%Y-%m-%d")
    joblib.dump(models[0], out / "evaluation_model.joblib")
    joblib.dump(models[1], out / "forecast_model.joblib")
    write_json(out / "model_features.json", {"order": FEATURES, "parameters": cfg["model"], "early_stopping": False,
        "selection": metrics.get("selection"), "missing_history": "native NaN support; current observation required"})
    if make_figures:
        figures(out, weekly, test, forecast, grid, mode)
    meta["elapsed_seconds"] = time.monotonic() - started
    write_json(out / "meta.json", meta)
    render(out / "dashboard.html", payload)
    atomic_text(out / "report.md", report_text(meta, cfg, metrics, worst))
    files = {str(p.relative_to(out)): {"sha256": file_hash(p), "bytes": p.stat().st_size} for p in sorted(out.rglob("*")) if p.is_file()}
    write_json(out / "manifest.json", {"meta": meta, "config": cfg, "environment": environment(), "ingestion": stats,
                 "source_ids": sorted(scene.item_id.unique()), "outputs": files, "source_metadata_file": "source_items.json",
                 "publication_note": "latest.json is updated only after this complete manifest is written"})
    write_json(root / "latest.json", {"run_id": run_id, "data_mode": mode, "dashboard": f"runs/{run_id}/dashboard.html", "manifest": f"runs/{run_id}/manifest.json"})
    return out
