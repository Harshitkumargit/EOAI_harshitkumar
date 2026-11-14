# Implementation validation

## Research revision ? 13 November 2026

The user completed 637-scene ingestion with zero failures. The assistant ran the revised pipeline with `--cached-only --out-dir outputs/research`: all 637 scenes reused, original live publication preserved, compatible cache `33570b657edd5813`. No package changes or new satellite downloads. The revision scores 1,161 cell-weeks and selects persistence. See [RESEARCH_AUDIT.md](RESEARCH_AUDIT.md) for results and limitations. Final checks: **33 tests passed** using global Python 3.10; the completed satellite dashboard passed desktop and narrow-window browser interaction/overflow checks; its desktop screenshot was visually inspected. All published artifact sizes and SHA-256 checksums were verified against the manifest. The latest audited run is `outputs/research/runs/20261113T173308Z-12621b86`. Original live pointer remains `20261113T114046Z-de07da2a`. Generic raster retries were regression-tested with fixtures, not a new remote outage. No field validation or new raw-source inspection is claimed.

## Historical implementation checks ? 12 November

The following records describe the earlier implementation, before the completed full run and research revision. Their pending-work statements apply to that historical date.

Checked on 12 November 2026 using the existing registered **Python 3.10.11** at `C:\Users\Lenovo\AppData\Local\Programs\Python\Python310\python.exe`. No package was installed or upgraded and no virtual environment was created. Plain `python` resolves to another interpreter; use `py -3.10`.

| Check | Observed result |
|---|---|
| `py -3.10 run.py --doctor` | All eight scientific/raster imports succeeded. |
| Installed dependency snapshot | Seven direct packages and 26 required installed packages recorded in requirements files. A fresh installation was not attempted. |
| `py -3.10 -m unittest discover -s tests -v` | **28 tests passed**, including temporary offline integration and figure generation. |
| Source compilation | `compileall` succeeded for package, entry point, scripts and tests. |
| Raw band loading/alignment | Tested with real local GeoTIFF fixtures through Rasterio/WarpedVRT; no remote pixels downloaded. |
| Masking/radiometry | Known NDVI, scale/offset, raw nodata, negative reflectance, masked arrays, SCL exclusions and empty-cell behaviour checked. |
| Forecast causality | Prefix-invariance, lag/next-target alignment, observed targets, complete-week boundaries and seasonal baseline alignment checked. |
| Catalogue/refresh | Duplicate-safe transaction, time/bbox queries, STAC relative paths, simulated scene failure/retry, checksum corruption detection and writer lock checked. |
| Evaluation | Chronological split, missing seasonal baseline, zero-error persistence, no-current-observation withholding and ranking eligibility checked. |
| Output integrity | Strict JSON, all-cell GeoJSON, separate model artifacts, checksums, atomic latest pointer and demo labels checked. |
| Browser interaction | Existing Chrome in headless mode: map-to-selector interaction, selector-to-history update, metrics/cards, matching map/cell counts, and no horizontal overflow passed at desktop and narrow-window sizes. |
| Visual inspection | Desktop/narrow screenshots and geographic PNG inspected. Horizontal overflow was found and fixed. Demo/historical labels remain visible. |
| Live three-scene access trial | The initial attempt discovered three scenes but DNS resolution failed for the COG host. On the next attempt, two scenes processed and one failed. The repeat reused those two cached scenes and processed the final scene: **three processed, zero failures, 10,579,763 bytes of local NDVI rasters**. No model was fitted. |
| Public source access | Python DNS lookup and HTTP byte-range requests succeeded for Earth Search and the first scene's red, NIR and SCL assets (HTTP 206). Rasterio/GDAL subsequently read and processed all three COG scenes through the cacheable trial runs. |
| Follow-up full-run failure supplied by user | The full ingestion found 402 scenes; three were cached and 399 failed with `Could not resolve host: sentinel-cogs.s3.us-west-2.amazonaws.com`. Repeating the old ingestion code could repeat that host-specific resolution failure. |
| AWS endpoint fallback fix | Ingestion now tries the regional path-style S3 hostname first, then dual-stack path-style and both virtual-host forms, with up to four attempts and 0.5/1/2-second backoff for temporary DNS/connection/timeout/HTTP errors. No dependency or credential changes. |
| Focused regression against failed scene | `S2C_43REP_20250418_0_L2A` loaded through the actual `load_scene` path using the new default regional path-style URL. It produced 120 scene rows; no full archive/model run was performed. |

The browser fixture used a **small nine-cell AOI, 100 m test grid and eight boosting iterations**, with generated observations. It is a software test, not the configured full 20 m experiment. Fixtures are isolated under `tmp/visual-check/`; they are not the user's default `outputs/live` or `outputs/demo` runs. Temporary unittest artifacts are removed after each test.

Two issues were found and corrected during validation: pandas' GroupBy `observed` property collided with column-style access (fixed using explicit column indexing), and long content/grid minimum sizes caused narrow-screen overflow (fixed with wrapping and zero-minimum grid tracks). Windows Chrome's minimum window size also clipped a 390-pixel screenshot; final narrow captures use a supported 600-pixel window. This is not a claim of testing every mobile device.

## Deliberately not run

- No full archive satellite ingestion/model run or full-run resource estimate. Three real scenes were read and processed in the earlier trial; one failed scene was subsequently re-read successfully after the endpoint fix. That does not prove every scene in the archive is available.
- No real forecasting metrics, crop-stress ground truth, field validation, real-scene visual inspection, or measured full-run resource estimate.
- No package installation, clean-environment rebuild, GPU setup, deployment, repository push or submission email.
- No external STAC schema-validation service or independently verified live publication-latency replay.

The user's real-data path is: run `py -3.10 run.py` -> inspect the new cache, rasters, metrics and report. The endpoint fix changes the source fingerprint and therefore creates a new processing-hash cache namespace; the earlier `data/live/c4626757a8246f73/` remains untouched. The actual full-run source selection, hashes, runtime and measured outcomes will be written by that run.

## Extended candidate study, 13 November 2026

Twelve candidates were evaluated using earlier-season folds, with checkpoints and fold sensitivity saved. The validation-selected median blend failed later development evaluation (MAE .077117 versus persistence .072351). The stable default retains the original three candidates and selects persistence. All35tests passed. No packages or scientific preprocessing were changed; no new imagery was downloaded. See [EXTENDED_RESEARCH.md](EXTENDED_RESEARCH.md) for citations, exact files and reproduction.

## 14 November radiometry verification update

Independent reference requests failed DNS resolution. Same-pixel comparison tooling and explicit provisional publication status are implemented; no calibration change or new accuracy claim is made.37tests and desktop/narrow browser checks passed. See [radiometry follow-up](RADIOMETRY_FOLLOWUP.md).

## Diagnostic hardening - 14 November 2026

Fixed three verified defects: offset hypotheses now include medians and differences on identical surviving pixels (separate-support summaries retained); the raw-pair tool rejects missing CRS, multiband imagery, noninteger/nonpositive/out-of-bounds windows and excludes nonfinite samples; the CLI now respects model.candidate_pool in config unless --candidate-pool is explicitly passed. Config validates candidate names early. Defaults remain stable when the setting is absent.

The AOI audit now returns a nonzero exit status for failed reads or missing requested scene IDs and records missing IDs, preventing empty/failed diagnostics from looking successful. Diagnostic JSON rejects NaN/Infinity. An empty land mask yields unavailable fractions, not a misleading zero.

All40tests passed, including exact common-support math, missing-CRS/infinite-value fixtures and CLI/config precedence. No production radiometry or target values changed. No new model-performance result is claimed. Existing outputs remain unchanged; the shared-support diagnostic was tested on known fixtures, not rerun successfully on remote imagery in this round.

Both original-product endpoint variants still fail DNS: see reference_access_20261114T064223312452Z.json. Independent source verification remains blocked by source connectivity. Do not expand the archive or select a new radiometry formula based only on apparent plausibility or model scores.
