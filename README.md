# Punjab Vegetation Watch

**Harshit Kumar | EO-AI Labs Role 01 | R1 / S1 / D1 / T2**

This historical Sentinel-2 prototype ranks approximately 3 km cells in the Ludhiana–Patiala belt by predicted next-week NDVI for an agriculture officer's inspection planning. The saved forecast targets the week of **27 April 2026**. It is an exploratory satellite replay, not a current crop-stress advisory.

## Review the submission

- Open [dashboard.html](dashboard.html) in a browser. The interactive map, shortlist, histories, and evaluation are embedded in one file; no server is needed.
- Read [technical_report.pdf](technical_report.pdf) for the four-page submission report. [report.md](report.md) is a text version with supporting detail.
- Read [ai_assistant_log.md](ai_assistant_log.md) for the required disclosure.
- Inspect [metrics.json](metrics.json), [test_predictions.csv](test_predictions.csv), and [forecast.csv](forecast.csv) for the saved evaluation and forecast.

The selected predictor is persistence. It scored 1,161 of 3,000 requested cell-weeks (38.7%), with MAE 0.072351 and RMSE 0.115787 NDVI units. Later-season results informed development, so this is not an untouched final test. No field-confirmed crop-stress labels were available. Radiometric calibration remains provisional; see [radiometry review](reports/RADIOMETRY_FOLLOWUP.md).

## Reproduce the pipeline

Use Python 3.10. In PowerShell, from this directory:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe run.py --doctor
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe run.py
```

The last command performs public Sentinel-2 ingestion and runs the pipeline end to end. It requires network access and substantial disk space. The 1.04 GB raster cache and SQLite catalogue are not included, so `--cached-only` cannot reproduce the saved satellite result from this folder alone. A separate `run.py --offline` mode produces clearly labelled synthetic demonstration data and is not satellite evidence. A fresh clean-machine or fresh-network rerun has not been verified.

The pipeline discovers scenes through Earth Search STAC, aligns and masks bands, computes cell-level NDVI, stores scene and feature records in SQLite, evaluates forecasting candidates on historical periods, and publishes a self-contained dashboard. [config.json](config.json) sets the area, dates, quality thresholds, and split. [docs/data_model_card.md](docs/data_model_card.md) records inputs, intended use, and limits. [docs/decisions.md](docs/decisions.md) records key implementation choices. [reports/validation.md](reports/validation.md) records checks performed during development.

## Development record: attempts, failures, and decisions

The following records the project's measured development sequence. AI assistance and the applicant's documented contribution are disclosed separately in [ai_assistant_log.md](ai_assistant_log.md). It does not imply that every implementation or check was performed personally by the applicant.

### 1. Establish a working data pipeline

The first objective was a refreshable path from public Sentinel-2 scenes to a weekly cell-level vegetation signal. A small ingestion trial tested source access before fitting a model. An early full retrieval attempt encountered DNS failures on the COG host: 399 scenes failed while three scenes were already cached. The ingestion adapter was changed to try equivalent regional and dual-stack AWS endpoints with bounded retries. Successfully completed scenes were retained so a retry did not restart the entire download.

The applicant subsequently completed ingestion of **637 scenes**, producing **76,440 scene-cell records with zero unresolved failures**. This establishes completion of that saved run, not uninterrupted future availability of the provider. Later generic TIFF read failures prompted exception-chain checks and bounded retries; metadata errors still fail immediately. [Implementation validation](reports/validation.md) records the historical checks.

### 2. Evaluate the original direct boosting model

The initial model predicted next-week NDVI directly using histogram gradient boosting. The pipeline worked, but the predictor did not beat carrying the current observation forward: on the same 698 observed cell-weeks, model MAE was **0.067023**, versus **0.065114** for persistence. Only **23.27%** of 3,000 requested cell-weeks were scored. Requiring complete older lag inputs discarded useful observed origin/target pairs.

This was a modelling and coverage limitation, not evidence that ingestion had failed. It motivated two changes: support missing older features while retaining observed origins and targets, and make persistence an explicit selectable predictor.

### 3. Improve coverage and select the predictor chronologically

The revision added observed-history count, current usable fraction, and observation-day count, and used HGB's missing-value support for older inputs. Missing targets were never filled. The action shortlist remained stricter: it requires four genuinely observed history weeks, so a numerical prediction is not automatically a recommendation.

Persistence, direct boosting, and residual boosting were compared on earlier-season rolling validation. Cells from the same target week stay together, with a one-calendar-week gap between fitting and validation. The objective is mean weekly MAE. Persistence won: **0.072884**, against **0.143942** direct and **0.148284** residual. The actual validation folds contain only 18, 33, and 305 rows, which limits confidence in the selection.

| Measurement | Original direct model | Revised stable policy |
|---|---:|---:|
| Earlier-season training rows / weeks | 444 / 17 | 942 / 20 |
| Scored cell-weeks / requested | 698 / 3,000 | 1,161 / 3,000 |
| Scored coverage | 23.27% | 38.70% |
| MAE on the same original 698 rows | 0.067023 | 0.065114 |
| RMSE on those same 698 rows | 0.098977 | 0.107832 |

Coverage increased by **15.43 percentage points**. Common-sample MAE improved by about **2.85%**, but RMSE worsened by about **8.95%**, indicating a worse squared-error outcome. The change was not uniformly more accurate. On the expanded 1,161-row sample, persistence MAE is **0.072351** and RMSE is **0.115787**; comparing these directly with the original 698-row scores would mix different samples. See the [comparison record](reports/revision_comparison.json) and [research audit](reports/RESEARCH_AUDIT.md).

Because later-season outcomes had already informed development, the revised result is explicitly a **development replay**, not an untouched confirmatory test. Relative skill and its bootstrap interval are zero because the chosen predictor is persistence; the forecast error itself is not zero.

### 4. Test alternatives and retain the simpler policy

A separate experiment compared twelve predefined candidates: persistence; direct and residual HGB; absolute-error variants; a shrunken residual correction; two ridge residual models; two median-history blends; and two conservative trend extrapolations. Selection still used only earlier-season folds. The research option is available through `--candidate-pool research`; the default remains `stable`.

A 25% median-history blend won earlier validation narrowly, but its later development-season MAE was **0.077117**, worse than persistence's **0.072351**. Lowest-ten overlap also fell from **0.475** to **0.450**. Fold winners were unstable. The experiment therefore supplied a negative result: adding these candidates did not establish a forecasting gain, and the stable policy was retained. [Extended research](reports/EXTENDED_RESEARCH.md) describes the candidates and [its comparison JSON](reports/extended_research_comparison.json) records the common-sample scores. Published literature results are context, not results reproduced by this project.

### 5. Investigate measurement quality before expanding the model

Large errors and inconsistent provider metadata led to a radiometry audit. For **590 of 637 scenes**, an item flag suggesting that an offset was already applied conflicts with nonzero asset offsets. This is a review flag, not proof that all those pixels are wrong.

Two scene samples showed that offset choice changes negative-reflectance rejection and NDVI summaries. The original summaries used different surviving pixel populations; the diagnostic was subsequently hardened to compare shared support. The hardened logic was checked on fixtures, not successfully rerun on remote imagery. Attempts to compare against independent original products failed with DNS errors. Accordingly, no correction was chosen from model scores, and production preprocessing and historical targets were preserved. The NDVI and reported accuracy remain **provisional**. See [radiometry follow-up and evidence](reports/RADIOMETRY_FOLLOWUP.md).

### 6. What the next step should establish

First, resolve calibration using red and NIR bands from the same original product on the same grid. If a correction is justified, reprocess into a new cache namespace and repeat the evaluation. Next, inspect large-error dates and changing valid-pixel support, add a justified crop mask and administrative boundaries, and collect longer earlier history. Reserve a fresh season before further tuning. Field observations, publication-latency checks, and refresh monitoring are required before an officer should act on this as an operational advisory.

The current outcome is a working, tested data-to-dashboard prototype with increased scored coverage and an honest baseline choice. It has not demonstrated learned-model superiority, field stress diagnosis, or operational readiness.

## Running individual checks and experiments

After the environment setup above, these commands use the same interpreter:

```powershell
# Inspect imports without downloading imagery.
.\.venv\Scripts\python.exe run.py --doctor

# Synthetic pipeline check; creates outputs/demo/runs/<run-id>/dashboard.html.
.\.venv\Scripts\python.exe run.py --offline

# Optional small access trial, followed by the full real-data command above.
.\.venv\Scripts\python.exe run.py --ingest-only --max-items 3

# Re-run earlier-season candidate selection using the included weekly table.
.\.venv\Scripts\python.exe scripts/research_experiment.py --weekly weekly.csv

# Independently recompute the saved metrics from the included prediction table.
.\.venv\Scripts\python.exe scripts/verify_submission.py
```

Each pipeline publication is saved in a new run directory. `outputs/demo/latest.json` or `outputs/live/latest.json` identifies the latest successful dashboard. A failed refresh does not replace an older result; always inspect its dates. The original saved dashboard at the package root remains a separate historical artifact.

The candidate experiment creates a new `outputs/research/experiment_<timestamp>/` directory containing `experiment.json` and candidate checkpoints. It selects using the earlier season only and does not score later-season targets. It can run from this ZIP without the omitted raster cache. The `--cached-only` commands in historical research notes require the original cache and are not standalone ZIP reproduction commands.

## Code guide and data contracts

| File | Responsibility and important rule |
|---|---|
| `pipeline.py` | Orchestrates ingestion, feature building, evaluation, and publication. Partial ingestion blocks publication unless explicitly allowed. |
| `config.py` | Validates this supported configuration and computes cache identity. |
| `ingest.py`, `preprocess.py`, `grid.py` | Fetch public STAC/COG data, align pixels, apply recorded radiometry and masks, and summarize fixed cells. |
| `catalogue.py` | SQLite transactions, completion checks, source lineage, raster checksums, and cache locking. |
| `features.py` | Complete weekly calendar, daily overlap selection, causal lag inputs, and observed next-week labels. |
| `selection.py` | Earlier-season folds, candidate fitting, equal-week MAE selection, and fold sensitivity. |
| `model.py` | Separate assessment and final forecast fits; shortlist eligibility and ranking. |
| `evaluate.py` | Paired errors, common-sample seasonal baseline, shortlist overlap, and temporal-block skill intervals. |
| `outputs.py`, `dashboard.py` | Publish measured outputs and a self-contained HTML asset, then atomically update the latest pointer. |

These modules are under `src/eoasset/`. Docstrings explain the temporal split, missingness, shortlist, and uncertainty rules. Cache identity hashes the bytes of ingestion, preprocessing, grid, and catalogue modules: even comment changes there can invalidate a cache. Those modules were not edited during submission cleanup. The source fixes to experiment-directory creation and generated-report wording are documented in [submission audit](reports/SUBMISSION_AUDIT.md).

The original saved output code hash identifies the historical run, not the later documented source revision in this ZIP. `manifest.json` hashes the files actually shipped. `pipeline_manifest.json` preserves the original run inventory and refers to excluded artifacts. Large rasters, the catalogue, original model checkpoints, and full scene metadata are not included; `weekly.csv` and `test_predictions.csv` support local numerical checking. Small comparison and diagnostic JSON records are included. Paths in historical records identify the original workspace and may not exist in this extracted package.

## Outstanding submission requirements

The applicant has confirmed that **R1/S1/D1/T2 matches the assigned configuration**.

The assignment requests an accessible Git repository link and a report attached to the email. Repository: https://github.com/Harshitkumargit/EOAI_harshitkumar. Include this link and either the dashboard asset or these local viewing instructions in the email. The submission deadline is seven days from receipt; the receipt date is not known from this package.
