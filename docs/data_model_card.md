# Data and model card

**Product:** Punjab Vegetation Watch. **Status:** prototype, user-selected R1/S1/D1/T2. Measured development-replay results and limits are recorded in [the research audit](../reports/RESEARCH_AUDIT.md).

## User, intended use and exclusions

A district agriculture officer in the Ludhiana-Patiala belt may use a relative vegetation shortlist to plan exploratory visits. Approximately 3 km analysis cells are not farms or administrative blocks. NDVI forecasts are not diagnoses of drought, disease or crop failure. Do not use the prototype for compensation, insurance, yield estimates or automated agricultural intervention.

## Inputs and transformations

Sentinel-2 L2A red/B04, nir/B08 and SCL COGs are discovered through Earth Search v1, collection `sentinel-2-l2a`. Contains modified Copernicus Sentinel data. Source IDs, metadata, timestamps, URLs, scale and offset are retained; asset access and availability depend on the public provider. Bbox [75.95,30.55,76.25,30.85] is a chosen study rectangle, not a sourced official boundary.

Rasterio aligns raw bands to EPSG:32643, 20 m. Explicit scale and offset are applied once. Raw zero/nodata, masked samples, negative reflectance and near-zero NDVI denominators are excluded. SCL classes 4 and 5 are retained; this is a land-quality filter, not a crop mask. Derived NDVI is saved as float32, nodata -9999.

The rasterized AOI is partitioned into clipped 3 km cells. Usable fraction divides valid pixels by all AOI pixels within a cell, including unavailable tile pixels in the denominator. A scene/cell needs >=0.30 to enter the weekly composite. One maximum-coverage scene per cell/day avoids duplicate same-day weighting; weekly median is a median of daily cell means, not a pixel mosaic. Coverage reported for the week is the minimum of contributing daily fractions, a conservative summary rather than spatial union coverage.

Only full Monday-Sunday weeks are used. One-week past-only fill may support historical lag inputs. Forecast origins and targets must be observed; filled-lag predictions are withheld from the action shortlist. No future interpolation is used. No rainfall, crop type, administrative boundaries or field observations are inputs.

## Model and evaluation

Persistence, direct HGB and residual HGB are compared using earlier-season temporal validation (up to three windows of four observed weeks, one-week gap). Mean weekly MAE selects the family; ties/no folds favor persistence. Current data select persistence. The inspected later season is now development replay, requiring fresh independent confirmation. Candidate and per-week scores are saved in metrics.json.

HistGradientBoostingRegressor: 200 iterations, rate .05, 15 leaves, minimum 20 rows/leaf, L2=1, seed 42, early stopping disabled. Boosting features: NDVI at lags 0/1/2/3, one-week change, four-week mean, annual sine and cosine, observed-history count, current usable fraction and observation-day count. Older inputs may be missing; origins and targets must be genuinely observed. Predictions are bounded to [-1,1]. These are fixed engineering defaults, not validated optima.

Assessment model train target weeks: 2024-11-04 through 2025-04-21. Test target weeks: 2025-11-03 through 2026-04-20. Same cells occur in train and test. Labels are later satellite NDVI, not independent crop-stress truth. Persistence and model share the primary scoring sample; the observed 52-week baseline uses a separately disclosed common sample. No seasonal value is filled for scoring.

Metrics: paired MAE/RMSE, skill relative to persistence, top-ten ranking overlap on weeks with >=20 eligible cells, counts/coverage, and a 500-replicate four-week moving-block bootstrap interval. All cells are retained together per sampled week. The interval is conditional on this limited historical sample and does not capture all spatial, sensor or deployment uncertainty. It is not a per-cell forecast interval.

A separate model refits on available observed targets up to the replay origin. It can include the formerly held-out season; it is never substituted for the assessment model. Joblib files require the recorded library environment and should only be loaded from trusted sources.

## Limitations and operational requirements

- Cloud/haze, changing valid spatial support, NDVI saturation, water exclusions, mixed crops/soil and harvest timing affect the signal.
- Selecting a best-coverage scene does not mosaic partial tiles; conservative coverage may discard otherwise recoverable observations.
- Small edge cells contain fewer pixels despite satisfying the same fractional rule.
- Missing cloudy targets can bias reported accuracy toward clear conditions.
- The relative shortlist does not imply that any cell is unhealthy; static land-cover differences can dominate ranking.
- Acquisition-week availability is assumed retrospectively. Historical provider publication latency is not reconstructed.
- A fixed historical cutoff is not a current forecast. Source timestamps, origin, target and generation time are displayed separately.
- A future year, different crop, area or observation regime may require retraining and new evaluation.

Before operational use: validate with an actual officer, compare against field/crop records, add crop masks and meaningful boundaries, collect longer holdouts, test fresh-data latency, monitor availability/drift and establish response procedures. Synthetic metrics are strictly software-test output.

## Reproducibility

Use README commands and the generated manifest. Config and processing source hashes isolate incompatible caches. SQLite transactions, raster checksums and atomic latest pointers protect reruns. The STAC export is a browsing representation of processed outputs; no hosted STAC service or formal external STAC validator is claimed. All current parameters and reasons are in FINALPLAN.md.

## Extended candidate study, 13 November 2026

Twelve candidates were evaluated using earlier-season folds, with checkpoints and fold sensitivity saved. The validation-selected median blend failed later development evaluation (MAE .077117 versus persistence .072351). The stable default retains the original three candidates and selects persistence. All35tests passed. No packages or scientific preprocessing were changed; no new imagery was downloaded. See [extended research](../reports/EXTENDED_RESEARCH.md) for citations, exact files and reproduction.
