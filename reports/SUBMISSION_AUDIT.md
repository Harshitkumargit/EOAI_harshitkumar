# Submission package audit

This record concerns the compact submission ZIP. The research reports retain their original dates and test counts; those counts describe different stages, not conflicting claims about one test run.

## Corrections

- Expanded the README with the documented sequence of retrieval failure, endpoint retries, completed ingestion, baseline failure, coverage revision, mixed error changes, unsuccessful candidate study, and unresolved calibration investigation.
- Included the six small JSON comparison/access/diagnostic records previously omitted. Added original-model and median-blend prediction tables under `reports/evidence/` so the reported common-sample comparisons can be recomputed locally.
- Fixed `research_experiment.py` to create parent directories on a fresh extraction. Previously it assumed `outputs/research` existed.
- Corrected generated report text to identify the candidate pool actually evaluated and to refer to the included README, model card, and disclosure instead of removed draft files.
- Added focused docstrings explaining missing inputs versus missing targets, shortlist eligibility, temporal fitting, residual learning, and bootstrap interpretation.
- Corrected the architecture note: conflicting radiometric metadata produces a provisional warning; it does not cause the adapter to fail automatically.
- Made `model.candidate_pool: stable` explicit in config.json so it matches the dashboard's saved configuration exactly. Its previous omission used the same default; this is not a change in predictor policy.
- Added `scripts/verify_submission.py` to recompute saved metrics and comparisons, check embedded dashboard data, validate local Markdown links, and verify packaged hashes.

## Provenance and scope

The root dashboard, metrics, forecast, report PDF, and scientific input tables are historical saved artifacts from run `20261114T063542Z-4aae3738`. Documentation and packaging fixes do not constitute a new satellite run. The original code hash in the output metadata remains historical. The package manifest describes the revised source and included evidence; do not replace the historical output code hash with the new source hash.

The ingestion, grid, preprocessing, and catalogue module bytes were preserved, so this documentation revision does not change their processing identity. No new remote imagery was fetched or radiometric correction selected. Fresh-environment installation and independent original-product calibration remain unverified.

The ZIP is a compact review package, not the complete original cache or experiment archive. Historical paths inside JSON and research notes identify the original runs. Their full raster caches, model checkpoints, source-item export, and catalogue are excluded. The included historical prediction tables and comparison JSON allow numerical checking without those large files.

## Submission requirements still unresolved

The applicant confirms R1/S1/D1/T2 matches the assigned configuration. The project has been published at https://github.com/Harshitkumargit/EOAI_harshitkumar. AI assistance remains disclosed. Neither this audit nor software tests establish field usefulness or operational fitness.

## Verification performed on 14 November 2026

- Extracted the rebuilt ZIP into a fresh directory and ran its own packaged source with Python 3.10. All 40 tests passed, including the synthetic pipeline integration test.
- Ran `scripts/research_experiment.py --weekly weekly.csv` from the fresh extraction with no existing output directory. It used 942 training rows, created twelve model checkpoints, and selected `median_25` with mean weekly validation MAE 0.0725461371. Persistence scored 0.0728843994. This reproduces earlier-season selection only; the included later-season prediction comparison remains the evidence for the blend's worse development result.
- Recomputed MAE, RMSE, coverage, seasonal common-sample errors, and ranking overlap from included CSVs. Recomputed both historical comparisons on matched cell/week targets. All matched the recorded JSON values.
- Confirmed the dashboard's embedded metrics, metadata, configuration, and spatial signals equal the standalone files. Local Markdown links resolve, included JSON parses without nonstandard NaN/Infinity values, and package hashes match.
- Confirmed the four cache-processing module files match the original workspace byte for byte. The installed Python 3.10 dependency metadata showed no conflicts among the pinned versions checked; a clean dependency installation was not performed.
- Checked ZIP integrity and safe relative entry paths. The four-page report PDF and its previously inspected figures were retained unchanged because its scientific figures and limitations remain consistent with the checked evidence.

These checks use the existing Python environment and saved tables. They do not constitute new satellite retrieval, independent pixel calibration, or field validation.

## Final archive cleanup

Removed the unused standalone histories figure and the redundant error_examples.json export. The interactive dashboard retains cell histories and error examples. The two report figures, source, tests, disclosure, reproducibility instructions, and numerical comparison evidence remain included. The original pipeline manifest is retained as a historical inventory and can name exports excluded from this compact package.
