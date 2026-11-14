# Research and results audit — 13 November 2026

The original model was slightly worse than persistence on MAE, not a failed ingestion pipeline. The completed original run contained 637 scenes with no failures. Its more serious modelling limitation was that only 698 of 3,000 requested test cell-weeks were scored. This audit improves coverage, model selection, diagnostics and error recovery; it does not establish operational crop-stress prediction.

## Evidence and comparison

Original result: `outputs/live/runs/20261113T114046Z-de07da2a`. Revised results are published separately under `outputs/research/runs/`; `outputs/research/latest.json` identifies the latest revision. The original live result is preserved. [revision_comparison.json](revision_comparison.json) records the exact two runs and a comparison on identical targets.

| Measurement | Original | Revised |
|---|---:|---:|
| Available source scenes | 637 | Same cached 637 |
| Earlier-season training rows | 444 | 942 |
| Earlier-season observed target weeks | 17 | 20 |
| Scored later-season cell-weeks | 698 / 3,000 | 1,161 / 3,000 |
| Evaluation coverage | 23.27% | 38.70% |
| Deployed predictor | Always direct boosting | Earlier-season selection chooses persistence |
| MAE on the **same original 698 rows** | 0.067023 | 0.065114 |
| RMSE on the **same original 698 rows** | 0.098977 | 0.107832 |

The common-sample MAE decreases about 2.85%, but RMSE increases about 8.95%. The original booster was better under the squared-error metric. The revision uses MAE as its selection objective, consistent with the project's primary metric; it is not uniformly more accurate. More evaluated rows means more honest coverage, not proof of improved prediction on those added rows.

Across all 1,161 revised rows, MAE is **0.072351**, RMSE **0.115787**, and skill versus persistence is **0** because persistence was selected. Comparing that MAE directly with the original 698-row MAE would mix different samples. No accuracy percentage or field-stress accuracy is implied by NDVI error.

## Findings and implemented corrections

| Finding | Evidence / consequence | Implemented response |
|---|---|---|
| Complete-history filtering discarded usable observed origins and targets | Original eight-feature readiness required all four lags even though HGB supports NaNs; only 444 training rows survived | Require a genuinely observed current origin; permit missing older inputs. Keep missing targets unscored. Add observed-history count, current valid fraction and observation-day count |
| Direct boosting was always selected | Original MAE 0.067023 versus persistence 0.065114; negative skill | Compare persistence, direct HGB and residual HGB on earlier-season validation. Save the selection evidence and selected model type |
| Coverage varied strongly by week | Many requested weeks/cells have no valid origin-target pair | Save observed-origin/target counts, per-week row counts/errors, and both pooled and equal-week MAE. Show low coverage visibly in the dashboard |
| Generic raster read failures escaped endpoint retries | User logs contained `TIFFReadEncodedTile` and `Read failed. See previous exception` | Traverse exception causes/contexts and recognize these signatures as eligible for bounded retries. Metadata validation errors still fail immediately |
| A transport-only source edit could invalidate hours of cache work | Processing identity includes ingestion source bytes | Map only the exact reviewed transport-only source hash to its previous identity. Future byte changes invalidate normally; tests protect both cases |
| A revised report could still describe every predictor as boosting | Persistence is now a possible saved model | Reports, model metadata and dashboard identify selection and distinguish persistence from the two learned candidates |
| Later-season results informed the audit | Original test results were already inspected | Label revised results **development replay**. Preserve the original run; require a fresh untouched season for confirmatory improvement claims |

No radiometry, SCL classes, scene cloud threshold, 30% usable-area threshold, source date window or target values were relaxed to raise the score. The 120-cell grid and the observed four-week shortlist rule remain. Missing-history numerical predictions do not automatically enter the action shortlist.

## Selection procedure and why these values

1. Construct eleven causal inputs: `lag0`, `lag1`, `lag2`, `lag3`, `delta1`, `roll4`, `sin_year`, `cos_year`, `history_count`, `valid_fraction`, `n_days`. `roll4` remains missing unless its four lag inputs exist. Quality inputs describe observation support; they are not confidence probabilities.
2. Pass **only earlier-season training rows** into `select_candidate`. Keep every cell from a target week in the same temporal partition. No shuffled row validation is used.
3. Use up to **three non-overlapping windows of four observed target weeks** toward the end of that training period. Four observed weeks provide multiple weekly observations; three windows limit fitting cost for the small history. These are engineering defaults, not paper-derived optima. Missing calendar weeks mean a window can span longer than 28 days.
4. Exclude fitting target weeks at or after validation start minus seven days. This leaves one calendar-week gap, matching the forecast horizon. It does not remove all temporal dependence or prove spatial independence.
5. Require at least the configured **100 fitting rows** and at least **four observed fitting weeks** for an inner fold. The outer experiment still requires eight training weeks. The inner four-week floor permits early folds in a single short season; sparse folds remain a limitation.
6. Compare three candidates: persistence predicts current NDVI; direct HGB predicts next NDVI; residual HGB predicts `next NDVI - current NDVI`, then adds current NDVI. The residual option tests whether learning a correction helps; no improvement is presumed.
7. Minimize mean of weekly MAEs so a clear week with many cells does not wholly dominate a cloudy week. This equally weights observed weeks, not every cell. Sparse weeks therefore have considerable influence. Stable ties, or no usable folds, choose persistence.
8. HGB settings stay at 200 iterations, learning rate .05, 15 leaves, minimum 20 rows/leaf, L2=1, seed42, two CPU threads, no automatic early stopping. This limits complexity and avoids introducing another random internal split. These settings have not been exhaustively optimized. Fit the selected family on all eligible earlier-season rows for assessment, then separately refit the same family on completed history for the final replay forecast.

Actual validation scores (mean weekly MAE):

| Candidate | Score |
|---|---:|
| Persistence | 0.072884 |
| Direct HGB | 0.143942 |
| Residual HGB | 0.148284 |

Validation windows contain only **18, 33 and 305 rows** respectively. Their starting target weeks are 2025-02-03, 2025-03-03 and 2025-03-31. The large imbalance and limited earlier-season history weaken confidence in selection. It would be inappropriate to claim that persistence always beats boosting or that these scores generalize to another year. Detailed folds are saved in `metrics.json`.

## What coverage numbers mean

Of 3,000 requested later-season cell-weeks, 1,532 have an observed origin, 1,532 an observed target, and 1,161 have both. Only 622 have an observed target plus four genuinely observed history weeks. The original 698 scored rows also allowed some one-week carried lags, which explains why that count exceeds 622.

The remaining 1,839 rows cannot be honestly scored under the current observed-origin/observed-target contract. Causes can include cloud masking, tile overlap, missing acquisitions, excluded water/land classes and the usable-area threshold. Counts alone cannot attribute them all to clouds. Increasing scored coverage from 23.27% to 38.70% still leaves substantial selection bias toward observed conditions.

## Research consulted and how it was applied

- **Roberts et al. (2017), “Cross-validation strategies for data with temporal, spatial, hierarchical, or phylogenetic structure,” Ecography 40, 913–929, DOI 10.1111/ecog.02881.** Dependence makes validation design central to the intended prediction task. Applied here by keeping weeks together and validating forward in time. This does not establish performance on new geographic cells. [Publisher](https://nsojournals.onlinelibrary.wiley.com/doi/10.1111/ecog.02881); [author-hosted full text](https://www.biom.uni-freiburg.de/mitarbeiter/dormann/roberts-et-al-2017-ecography.pdf/at_download/file).
- **Hyndman and Athanasopoulos, Forecasting: Principles and Practice, third edition, chapter 5.** Provides naive benchmarks and evaluation with past-only training at successive forecast origins. Applied as a persistence candidate and forward validation; the project's multiweek windows and equal-week MAE are explicit adaptations. [Open textbook](https://otexts.com/fpp3/toolbox.html#time-series-cross-validation).
- **Zhu, Wang and Woodcock (2015), “Improvement and expansion of the Fmask algorithm: cloud, cloud shadow, and snow detection for Landsats 4–7, 8, and Sentinel 2 images,” Remote Sensing of Environment 159, 269–277, DOI 10.1016/j.rse.2014.12.014.** Supports treating atmospheric contamination as a measurement-quality concern. It motivates preserving masks and inspecting imagery. This project uses provider SCL, not Fmask; the paper does not validate this project's SCL masks or thresholds. [DOI](https://doi.org/10.1016/j.rse.2014.12.014); [author-hosted full text](https://gerslab.cahnr.uconn.edu/wp-content/uploads/sites/2514/2021/06/Improvement-and-expansion-of-the-Fmask-algorithm-cloud-cloud-shadow-and-snow-detection-for-Landsats-4%E2%80%937-8-and-Sentinel-2-images.pdf).
- **scikit-learn 1.5 HGB documentation.** Confirms native support for missing input values. Applied to missing historical features, never to fabricated labels. [Versioned estimator documentation](https://scikit-learn.org/1.5/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html).

The papers justify methodology and limitations, not the exact numerical hyperparameters or a claimed accuracy gain. The research connector stalled; available web retrieval and author-hosted papers supplied the sources above. No inaccessible full paper is represented as read.

## Remaining improvements in priority order

| Priority | Next experiment | Why / condition |
|---|---|---|
| 1 | Collect more earlier complete seasons; reserve one fresh future season untouched | 942 correlated cell-weeks are not 942 independent seasonal examples. More years support stable temporal selection; requires additional ingestion |
| 1 | Inspect largest-error cells against dated red/NIR/SCL imagery and crop/field records | Distinguish real harvest/land-cover change from changing spatial support or contamination; no physical diagnosis is available from error size alone |
| 1 | Test daily pixel mosaics before cell aggregation | Existing best-scene selection can discard complementary tile coverage. Must prevent overlap double counting and revalidate radiometry/masks; requires a new processing namespace |
| 2 | Add a dated, licensed crop mask and meaningful field/administrative boundaries | Current cells mix crops, bare ground and other land. Land filtering is not crop identification; compare coverage and errors before adopting |
| 2 | Test cloud-search threshold and 20/30/50% cell-coverage sensitivity on training data | Scene cloud percentage may exclude scenes with a clear AOI; changing support affects the target. Do not choose thresholds on this inspected later season |
| 2 | Compare no carry versus one-week carry, MAE-loss boosting, regularized linear trend and carefully bounded corrections | Potentially useful low-cost experiments; need stronger validation history before a broad search. Do not endlessly tune on 18-row folds |
| 3 | Add acquisition/publication latency and operational monitoring | Acquisition week currently approximates data availability. A retrospective forecast is not proof data were available at that historical moment |
| 3 | Reassess GPU only for a justified larger model | The current learner is CPU HGB; persistence does almost no fitting. Four GB VRAM cannot repair DNS, observation gaps or inadequate training history |

No LSTM/Transformer, rainfall input, crop mask, local SAFE adapter or GPU training capability is claimed as implemented. Adding them merely to use installed libraries would change the experiment without evidence of benefit.

## Reproduce and review

```powershell
py -3.10 -m unittest discover -s tests -v
py -3.10 run.py --cached-only --out-dir outputs/research
$latest = Get-Content outputs/research/latest.json -Raw | ConvertFrom-Json
Start-Process (Join-Path outputs/research $latest.dashboard)
py -3.10 scripts/compare_runs.py outputs/live/runs/20261113T114046Z-de07da2a (Join-Path outputs/research "runs/$($latest.run_id)") --output reports/revision_comparison.json
```

No manual dataset download is needed for this revision. Cache `33570b657edd5813` is reused, and the original live dashboard remains unchanged. The hash compatibility exception is restricted to the exact transport-only revision, not permission to reuse rasters after scientific preprocessing changes. No global packages were installed, upgraded or removed.

See [validation.md](validation.md) for actual checks. This is a source/results audit and software regression check, not an exhaustive security audit, independent replication, remote-network reliability test, or field validation. An applicant still needs to review the images, report limitations truthfully and retain a fresh evaluation period before making improvement claims.

## Final validation record

Final audited run: `outputs/research/runs/20261113T173308Z-12621b86`. All 33 tests passed. Desktop and narrow browser checks passed; the desktop screenshot was inspected. Published file sizes and SHA-256 checksums match the manifest. The five largest displayed errors are all for target week 2025-12-22, including B120 (observed about 0.785 versus predicted 0.069) and B017 (about 0.059 versus 0.733). This concentration makes that week a priority for source-image and spatial-support inspection; it does not establish whether the cause is masking, land-cover change or another effect. No rows were removed simply for having large errors.
