# Architectural decisions

1. **Use installed Python 3.10.** Inspection found the needed scientific/raster libraries there, while plain `python` resolves elsewhere. The user explicitly requested no installs/upgrades. `run.py` supports running the src package without editable installation.
2. **Static HTML asset.** A single self-contained file satisfies the assignment's visual/narrative requirement, works offline and avoids adding Streamlit. SVG map coordinates come from clipped GeoJSON, and all text/data are embedded safely. There is no remote basemap.
3. **SQLite as catalogue and feature store.** Standard-library transactions provide a consistent completion ledger and duplicate protection without a server. Every source and scene/cell feature is queryable. STAC-style JSON is derived for interoperability, not a competing ledger.
4. **Rasterio instead of an additional loader stack.** WarpedVRT supplies an explicit fixed grid, CRS transforms and raw pixel reads. Rasterio also creates masks and cell polygons, so GeoPandas/Shapely/PyProj are unnecessary direct dependencies.
5. **Explicit but provisional radiometry.** The adapter applies per-asset scale and offset and rejects missing scales or invalid numeric metadata. It does not resolve contradictory item flags: these are recorded as publication warnings. Pixel magnitudes and baseline-only guesses cannot reliably identify harmonized COGs. Independent original-product verification is still required; see [radiometry follow-up](../reports/RADIOMETRY_FOLLOWUP.md).
6. **Causal forecasting and observed targets.** A full-series interpolation can use future data. Only optional past carry is allowed for lags; its presence is visible. Temporal train/test windows use target dates, not random row splits.
7. **Existing scikit-learn boosting.** Histogram boosting handles a small CPU regression task without LightGBM installation. Complexity is deliberately restricted. Persistence remains a first-class baseline; improvement is not guaranteed.
8. **Coverage and abstention.** All cells remain visible. Origins with missing data are withheld, as are action recommendations with carried lag values. Top-N evaluation matches the shortlist policy and does not rely on an unrelated z threshold.
9. **Immutable output runs.** A failed run cannot partially overwrite the last complete report. Each published run has a manifest and hashes; the atomic latest pointer is the commit marker. Old results remain historical and dated.
10. **Honest delivery scope.** The user runs the full satellite pipeline. Automated temporary synthetic tests verify code contracts, not real performance. No fabricated metric, operational validation, deployment or submission claim is made.

## Research revision ? 13 November 2026

The 13 November audit adds training-only selection among persistence/direct/residual boosting, native missing-history support, coverage diagnostics and an exact hash alias for the reviewed transport-only retry fix. The user completed full ingestion; the assistant subsequently evaluated cached data. See ../reports/RESEARCH_AUDIT.md for measured evidence and remaining limitations.

## Extended candidate study, 13 November 2026

Twelve candidates were evaluated using earlier-season folds, with checkpoints and fold sensitivity saved. The validation-selected median blend failed later development evaluation (MAE .077117 versus persistence .072351). The stable default retains the original three candidates and selects persistence. All35tests passed. No packages or scientific preprocessing were changed; no new imagery was downloaded. See [extended research](../reports/EXTENDED_RESEARCH.md) for citations, exact files and reproduction.
