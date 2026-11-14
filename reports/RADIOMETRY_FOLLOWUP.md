# Radiometry follow-up ? 14 November 2026

Provider-specific evidence changes the previous assessment: following asset-level scale/offset documentation is not sufficient to establish correctness for this legacy collection.

Earth Search discussion26 describes historically subtracting the offset during COG creation: https://github.com/Element84/earth-search/discussions/26 . Issue71 reports cross-provider pixel comparisons showing incorrect offsets: https://github.com/Element84/earth-search/issues/71 . Issue66 reports that even the already-applied flag can be wrong: https://github.com/Element84/earth-search/issues/66 . These are provider-hosted discussion and user reports, not confirmation that every scene in this project is affected.

A new independent script, scripts/audit_radiometry.py, reads two suspicious December scenes, samples the AOI at256x256, retains raw TIFF and asset metadata and compares negative-reflectance fractions and NDVI under offsets-.1 and0. It writes timestamped JSON reports and never modifies production data. TIFF default scale1/offset0 is not proof of physical calibration.

The initial diagnostic failed on a Grid width attribute and was corrected to use labels.shape; its failed report is retained. Successful raw-sample evidence, if available, is in the later radiometry_sample JSON. Plausible values alone cannot resolve the offset: compare identical pixels against independently calibrated source products before changing the production adapter. Never choose radiometry by whichever setting gives a better model score.

No production preprocessing, cache or previous result was changed. If raw comparison confirms a correction, reprocess in a distinct namespace; derived NDVI alone cannot reconstruct discarded raw red/NIR measurements.

## Completed raw sample

Both scenes were read successfully. Evidence: [radiometry_sample_20261114T055935861385Z.json](radiometry_sample_20261114T055935861385Z.json). On Dec22, applying-.1 makes33.68% of sampled SCL4/5 pixels negative; retained median NDVI is.560, versus.323 under zero offset. Dec27 negative fraction is4.49%, median.122 versus.101. The retained pixel populations differ, so these are diagnostic summaries, not paired biological changes or validated corrected values. This strengthens the need for an independent source comparison; it does not prove the correct offset. Only two scenes were sampled, with nearest-neighbor resampling; full production aggregates were not recomputed.

## Implemented verification and publication changes

Added `scripts/compare_radiometry.py`: compares original reference DN against COG DN on an exact shared grid, excludes nodata/clamped pixels, requires100paired pixels, and records differences near0 and1000DN. Accepts local original JP2 files or HTTPS. It never selects or applies a correction automatically. Product acquisition, baseline and band identity must be verified independently; geometry equality alone is insufficient.

Added publication-level `radiometry_status.json`, a manifest-linked conflict inventory, a metrics status and prominent report/dashboard notice. Satellite results are provisional even if an item has no obvious metadata conflict, because provider flags can be wrong. Synthetic demonstrations are marked not applicable. No ingestion source or processing hash was changed.

Actual independent-source attempts failed with DNS resolution errors, including the original JP2 host, reference catalogue and final regional S3 comparison. The exact failed pair attempt is retained in `radiometry_pair_20261114T063606247533Z.json`. This is not a successful independent pixel comparison and does not establish a correct offset.

Validation:37tests passed, including exact1000DN/0DN fixtures, grid mismatch rejection, bounds checks and metadata-status handling. Desktop/narrow browser checks passed. All published artifact hashes verified. New provisional run: `outputs/research/runs/20261114T063542Z-4aae3738`;590of637scenes flagged. Existing caches and original live results preserved; no packages changed. Model accuracy is unchanged.

Reproduction with matching original local source files:

```powershell
py -3.10 scripts/compare_radiometry.py --cog PATH_TO_B04_COG.tif --reference PATH_TO_SAME_PRODUCT_B04.jp2 --window 1200 8000 128 128
py -3.10 -m unittest discover -s tests -v
py -3.10 run.py --cached-only --candidate-pool stable --out-dir outputs/research
```

The window is a reproducible example; ensure it contains valid shared pixels. Obtain red and NIR reference bands from the exact saved product identity, not merely a nearby date or different reprocessing baseline. Once access is restored, compare multiple scenes/bands before defining a correction policy. Only then reprocess affected data in a distinct namespace and assess models. Increasing the dataset before this would repeat an unresolved calibration assumption.

## Diagnostic hardening - 14 November 2026

Fixed three verified defects: offset hypotheses now include medians and differences on identical surviving pixels (separate-support summaries retained); the raw-pair tool rejects missing CRS, multiband imagery, noninteger/nonpositive/out-of-bounds windows and excludes nonfinite samples; the CLI now respects model.candidate_pool in config unless --candidate-pool is explicitly passed. Config validates candidate names early. Defaults remain stable when the setting is absent.

The AOI audit now returns a nonzero exit status for failed reads or missing requested scene IDs and records missing IDs, preventing empty/failed diagnostics from looking successful. Diagnostic JSON rejects NaN/Infinity. An empty land mask yields unavailable fractions, not a misleading zero.

All40tests passed, including exact common-support math, missing-CRS/infinite-value fixtures and CLI/config precedence. No production radiometry or target values changed. No new model-performance result is claimed. Existing outputs remain unchanged; the shared-support diagnostic was tested on known fixtures, not rerun successfully on remote imagery in this round.

Both original-product endpoint variants still fail DNS: see reference_access_20261114T064223312452Z.json. Independent source verification remains blocked by source connectivity. Do not expand the archive or select a new radiometry formula based only on apparent plausibility or model scores.
