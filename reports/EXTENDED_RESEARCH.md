# Extended forecasting research and experiment record

13 November 2026. This extends, rather than replaces, [RESEARCH_AUDIT.md](RESEARCH_AUDIT.md). The repository layout, original datasets, masks, targets, outputs and model checkpoints were preserved.

## Outcome

**No new accuracy improvement was demonstrated.** Twelve predeclared candidates were fitted and evaluated on earlier-season folds. A recent-history blend narrowly won validation but failed on the later development season. It remains an explicit research option; the established three-candidate policy is the default and continues to select persistence. This is a negative experimental result, not a claimed model breakthrough.

The project now has integrated, serializable robust-loss, linear-residual and recent-history candidates, immutable experiment records, all-candidate training checkpoints, fold-level errors and selection-stability diagnostics. No packages were installed or changed. No new satellite pixels were downloaded.

## Exact problem and constraints

Forecast observed next-week cell-mean Sentinel-2 NDVI for 120 approximately 3 km cells in the selected Punjab rectangle. Inputs are eleven causal lag/seasonality/quality features. The earlier season supplies 942 usable rows across only 20 target weeks; these are spatially and temporally correlated, not 942 independent seasonal examples. Later-season evaluation has 1,161 rows out of 3,000 requested cell-weeks. Missing cloud-filtered targets stay missing. This is neither crop-stress classification nor satellite-image generation.

Dependencies remain: `pipeline.py` -> `features.py` -> `model.py` -> `selection.py`/`evaluate.py` -> `outputs.py`/dashboard. Ingestion, radiometry, grid, catalogue and scene cache identity are unchanged in this round. Final forecast refitting remains separate from assessment. Earlier full-series inspections mean all revised later-season results are development evidence.

## Research scope and access

Parallel research investigated vegetation forecasting and low-data forecasting separately, while a third read-only audit inspected large-error cases. Sources accessed include arXiv, CVPR/NeurIPS/AAAI proceedings, Nature, author-hosted PDFs, publisher abstracts, official GitHub repositories and Hugging Face model cards. The Firecrawl research connector was actually attempted but returned a transport error; browser retrieval supplied the usable evidence. No private code/data were sent to external research services. Google Scholar, Semantic Scholar, IEEE Xplore, PubMed and Papers With Code are not claimed as accessed merely because they were requested as possible routes. Medical imaging conferences are not directly relevant to this task.

“Full methods/results” below means relevant sections of accessible full text were inspected, not every cited paper independently verified. Published metrics use different data and cannot be substituted for this project's experiments.

| Study / verified source | Access, method and evidence | Decision for this project |
|---|---|---|
| Iele et al. (2026), *Probabilistic NDVI Forecasting from Sparse Satellite Time Series and Weather Covariates*, [arXiv2602.17683v1](https://arxiv.org/html/2602.17683v1) | Preprint full methods/results. Two transformer branches for history/future covariates, quantiles .1/.5/.9, median point prediction; GreenEarthNet Europe, 24,861 cubes. Reported MAE .0509/RMSE .0821. Cloud-obscured acquisition NDVI is interpolated; future weather experiments use perturbed observed weather | Motivates median/absolute-error loss, not filling our labels or using realized future weather. Their age weight is constant at our fixed seven-day horizon. [Code](https://github.com/arco-group/ndvi-forecasting), [checkpoint](https://huggingface.co/ireneiele/agrimatnet-vegetation-forecasting) require a different 28-feature weather-inclusive contract |
| Benson et al. (CVPR2024), *Multi-modal Learning for Geospatial Vegetation Forecasting*, [paper](https://openaccess.thecvf.com/content/CVPR2024/html/Benson_Multi-modal_Learning_for_Geospatial_Vegetation_Forecasting_CVPR_2024_paper.html) | Full methods/results/appendix. Contextformer combines vision, temporal attention, weather and topography; predicts change relative to last clear NDVI. Reported RMSE .14 over100days and .08 first25days. Delta-prior ablation supports the prior; larger16M model did not help | Motivates persistence-anchored residuals. Millions of parameters and large European image training are not justified for942rows. [Official code](https://github.com/vitusbenson/greenearthnet) |
| Requena-Mesa et al. (2021), *EarthNet2021*, [full paper](https://arxiv.org/pdf/2104.10066) | Dataset/baseline sections inspected. Over32,000 samples,30five-day128x128frames with weather/topography. Persistence averages clear context pixels; IID EarthNetScore .2625 versus Channel-U-Net .2902 | Motivates causal recent-level baselines. Image-composite scores are not comparable to cell NDVI MAE; observed future weather makes the conditional task different |
| Zhao et al., *VegeDiff*, [2024 full preprint](https://arxiv.org/html/2407.12592v1), [official code](https://github.com/NJU-LHRS/Official_VegeDiff) | Full methods/results passages; latent diffusion, VAE on approximately10M Satlas images, weather-conditioned attention. Preprint NDVI RMSE .13 versus persistence .23 on EarthNet2021X; multi-A100 training. Later journal version surfaced; numerical claims here refer to inspected preprint | Reject architecture transplant on4GB GPU and tiny cell table. Bidirectional cloud filling needs causality review; no implementation attempted |
| Chen et al. (2024), *A new deep learning-based model for reconstructing high-quality NDVI time-series data in heavily cloudy areas*, [DOI10.1080/17538947.2024.2407941](https://doi.org/10.1080/17538947.2024.2407941), [author PDF](https://srs.bnu.edu.cn/docs/2025-03/3f620c6487a34a00b5345361c1dfd4b9.pdf) | Architecture sections inspected. Bidirectional recurrent Sentinel1/2 reconstruction with96-unit LSTMs and consistency loss,8day series. Abstract example RMSE .075 versus .108 GF-SG | Reconstruction is not causal forecasting. Radar fusion requires a new data experiment; do not fabricate forecast truth from bidirectional estimates. Official code not verified |
| Garioud et al. (2021), *Recurrent-based regression of Sentinel time series for continuous vegetation monitoring*, [publisher](https://www.sciencedirect.com/science/article/abs/pii/S0034425721001371) | Abstract/method excerpts only; SenRVM multivariate Sentinel1 regression toward6day NDVI, multiple land covers | Potential radar-based monitoring alternative, not a plug-in NDVI-only forecaster. No full-paper or reproduced metric claim |
| *DeepGrass* (RSE2026), [DOI10.1016/j.rse.2026.115545](https://doi.org/10.1016/j.rse.2026.115545) | Primary indexed abstract only, full retrieval blocked. Forecasts10bands/28indices over15days;565,614 Swedish fields,2020–22 training and later2023 geographic/year evaluation. Abstract NDVI RMSE .028 day1 to .105 day15 | Much larger crop-specific dataset; supports independent-year validation, not expected Punjab gains. Mowing/grazing interventions excluded; official code not verified |
| Gardner & McKenzie (1985), *Forecasting Trends in Time Series*, [DOI](https://doi.org/10.1287/mnsc.31.10.1237), [author PDF](https://www.bauer.uh.edu/egardner/3301H%20Operations%20Management/ESG%20Publications/1985%20Forecasting%20trends.pdf) | Full methodology/empirical sections; damped exponential-smoothing trend,1,001series, percentage-error comparisons | Motivation for controlled extrapolation only. Our scaled one-week delta is **not** a reproduction of fitted Holt damping |
| Wang et al. (2023), *Forecast combinations: an over50-year review*, [author metadata](https://robjhyndman.com/publications/combinations/), [full preprint](https://arxiv.org/pdf/2205.04216) | Relevant full-text sections on combinations, shrinkage and estimation uncertainty | Motivates a small fixed blend grid. Exact weights are engineering choices; no high-dimensional stacking on sparse folds |
| Montero-Manso & Hyndman (2021), *Principles and algorithms for forecasting groups of time series: locality and globality*, [author page](https://robjhyndman.com/publications/global-forecasting/) | Abstract/author overview only; full retrieval failed. Local versus pooled forecasting functions | Supports considering pooled predictors; does not establish independence or cross-region performance |
| Grinsztajn et al. (NeurIPS2022), *Why do tree-based models still outperform deep learning on typical tabular data?*, [full paper](https://proceedings.neurips.cc/paper_files/paper/2022/file/0378c7692da36807bdec87ab043cdadc-Paper-Datasets_and_Benchmarks.pdf), [code](https://github.com/LeoGrin/tabular-benchmark) | Method/results inspected;45tabular datasets, tuned trees/neural architectures, accuracy and R-squared | Retain inexpensive tree baselines; this is not proof trees always win or a temporal-NDVI benchmark |
| Zeng et al. (AAAI2023), *Are Transformers Effective for Time Series Forecasting?*, [inspected preprint v2](https://arxiv.org/html/2205.13504v2), [code](https://github.com/cure-lab/LTSF-Linear) | Architecture/results inspected; linear/decomposition models, nine datasets, long-horizon MSE/MAE | Motivates linear baseline. Our ridge residual is not DLinear; kernel25 and96-point context do not fit four lags |
| Ansari et al. (2024), *Chronos*, [full HTMLv2](https://arxiv.org/html/2403.07815v2), [code](https://github.com/amazon-science/chronos-forecasting), [46M small model](https://huggingface.co/amazon/chronos-t5-small) | Methods/results overview/limitations read. Quantized-token T5 forecasting pretrained on public/synthetic series;42datasets, MASE/WQL. Insufficient context can miss trends | Optional future zero-shot test. `chronos` is not installed; no package/weight download or VRAM-fit claim |
| Hollmann et al. (Nature2025), *Accurate predictions on small data with a tabular foundation model*, [full article](https://www.nature.com/articles/s41586-024-08328-6), [code](https://github.com/PriorLabs/TabPFN) | Methods/results/limits inspected. Synthetic-prior transformer,29classification/28regression datasets <=10Krows. Pretraining generator unreleased; time-series-specific priors discussed as future work | Corrects blanket claims that neural models cannot work on small tables. Temporal shift remains unverified; `tabpfn` is not installed, so no execution or installation |

The earlier audit additionally cites temporal validation (Roberts et al.), forecasting benchmarks (Hyndman/ Athanasopoulos), cloud quality (Zhu et al.) and versioned scikit-learn missing-value support. Search was targeted to methods that could change a decision, not to collecting irrelevant citations.

## Predeclared candidates and mathematical definitions

Let p be current observed NDVI and x the existing eleven inputs. Every output is clipped to [-1,1] in the model orchestration. Targets and quality filters stay fixed.

- `persistence`: prediction=p.
- `direct`, `residual`: original squared-error HGB; respectively predict y or predict y-p then add p.
- `absolute_direct`, `absolute_residual`: same architecture, `loss=absolute_error`, targeting the conditional median appropriate to MAE.
- `shrink_residual`: p + .25 times the absolute-error residual estimate. Restricting correction size trades potential bias for stability.
- `ridge_10`, `ridge_100`: predict y-p using standardized current level, lag1..3 minus current level, missingness flags, annual features and quality summaries. Missing relative differences become0 with flags. StandardScaler is fit only on fitting rows, then Ridge with alpha10 or100. These are stronger regularization alternatives, not optimized constants.
- `median_25`, `median_50`: p+w(median(lag0..3)-p), w=.25 or.50. Median ignores missing entries; existing one-week carried inputs may participate. This is a robust causal level blend, not a cloud-corrected observation or named-paper reproduction.
- `trend_25`, `trend_50`: p+w(p-lag1), w=.25 or.50; missing lag1 gives zero change. These are bounded-strength delta candidates, not fitted Holt models.

Original HGB settings remain200iterations, learning rate.05,15leaves,min20rows/leaf,L2=1,seed42,two threads,no automatic early stopping. Alpha10/100 and blend.25/.50 were fixed before running the expanded study, to span a small conservative range rather than optimize the inspected later season. No broad architecture search, target filtering or mask weakening occurred.

## Experiment protocol and measured results

`scripts/research_experiment.py` truncates weekly input at the earlier training end **before constructing targets**. It saves source hash, config, code hash, environment, timing, all12 fitted training checkpoints and validation detail. Three four-observed-week validation windows with one-calendar-week gaps match the existing protocol. Mean weekly MAE is the selection objective. Their row counts remain18,33,305; all cells of a week stay together.

| Candidate | Earlier-season mean weekly MAE |
|---|---:|
| Persistence | .072884 |
| Direct HGB | .143942 |
| Residual HGB | .148284 |
| Absolute direct HGB | .110681 |
| Absolute residual HGB | .114962 |
| Shrunk absolute residual | .075224 |
| Ridge alpha10 | .335898 |
| Ridge alpha100 | .183200 |
| Median blend25% | **.072546** |
| Median blend50% | .074914 |
| Trend25% | .082210 |
| Trend50% | .096092 |

The median25 winner improves validation by only0.46%. Its three fold scores are .069238/.052600/.095801 versus persistence .074494/.053638/.090521. It loses the last fold. Leaving out fold0 selects shrink_residual; omitting fold1 selects persistence; omitting fold2 selects median25. That instability is now saved automatically. There was no second hyperparameter search after viewing later-season scores.

Only the selected candidate was then evaluated on the later development season:

| Same1,161 observed targets | Established persistence | Experimental median25 |
|---|---:|---:|
| Pooled MAE | .072351 | .077117 |
| RMSE | .115787 | .117613 |
| Equal-week MAE | .062003 | .063467 |
| Top10 overlap,8eligible weeks | .475 | .450 |

The experiment worsens MAE6.59%. The skill bootstrap interval is approximately[-.1274,.0502], not evidence of improvement. The default therefore retains the established selection policy. This retention decision was made after development evaluation and must not be marketed as a new untouched test result. No additional later-season candidate mining was performed.

## Data-error investigation and unresolved concerns

The largest errors concentrate in specific weeks. B017 moves .733448 (Dec15) -> .059199 (Dec22) -> .830914 (Jan5); the Dec22 weekly value comes from Dec27, while a nearly clear Dec22 acquisition's .692064 is excluded because its cell usable fraction is .215778. These are changing-support observations, not verified biological jumps. The Dec22 target week has61rows/MAE.243640; Apr13 has119rows/MAE.206304. High errors were retained.

All637 saved red assets have scale.0001/offset-.1;590 also carry `earthsearch:boa_offset_applied=True`. This item-level flag appears ambiguous against asset-level metadata. **A double-offset bug is not established.** [Official Earth Search documentation](https://raw.githubusercontent.com/Element84/earth-search/main/docs/collections/sentinel-2-l2a.md) instructs applying nonzero asset offset after scale, which matches the current code. Raw COG/tag/provider investigation is still required; changing the formula based only on the flag would be unjustified. Since only derived NDVI is cached, confirmed radiometric corrections would require raw-band rereads and a new namespace.

Further model tuning on this short, unstable validation sample has little convincing benefit. The priority is independent raw-image/support verification, more earlier seasons, crop-specific support and a fresh future evaluation season. Radar/weather inputs require actual data and issue-time availability checks. The literature does not remove these requirements.

## Preservation, modified files and reproduction

Git reported the project untracked inside a parent repository; no reset, commit, rename or deletion was performed. Pre-edit sources/config/docs/tests are archived in `reports/source_baseline_20261113T174924Z.zip`. Historical checkpoints and publications remain under their original `outputs/live`, `outputs/demo` and `outputs/research/runs` paths. The original live pointer remains unchanged.

Modified existing files: `selection.py` (candidate implementations, explicit pools, fold diagnostics), `pipeline.py` (pool CLI), `outputs.py` and `dashboard.html` (accurate method description), `tests/test_revision.py` (blend math, missing inputs, scaler separation, serialization). New minimal files: `scripts/research_experiment.py`, this record and `extended_research_comparison.json`. README and supporting guides link this result. Scientific preprocessing/config values are unchanged.

Preserved experiment checkpoints: `outputs/research/experiment_20261113T175111492783Z` (initial study) and `experiment_20261113T175249248921Z` (same candidates with fold-sensitivity diagnostics). Failed candidate publication: `outputs/research/runs/20261113T175307Z-73f72714`. [Measured comparison](extended_research_comparison.json). The repeated training-only study reproduces scores; it is not independent evidence.

```powershell
# Reproduce the bounded study without scoring later-season candidates
py -3.10 scripts/research_experiment.py --weekly outputs/research/runs/20261113T173308Z-12621b86/weekly.csv
# Established default, compatible satellite cache, no downloads
py -3.10 run.py --cached-only --candidate-pool stable --out-dir outputs/research
# Explicitly reproduce the unsuccessful experimental policy if desired
py -3.10 run.py --cached-only --candidate-pool research --out-dir outputs/research
py -3.10 -m unittest discover -s tests -v
```

All35tests passed, including synthetic publication and the new candidate checks. These tests establish code contracts, not superior predictive accuracy. Existing global Python3.10 and installed scientific packages were used. Torch and XGBoost are discoverable, while Chronos/TabPFN/LightGBM are not; availability alone did not justify unrelated model additions. No GPU training, pretrained-weight download, field validation or raw radiometry repair is claimed.

Final retained-default publication: `outputs/research/runs/20261113T175405Z-995b7ed7`. Desktop and narrow browser checks passed. All18published artifact hashes/sizes were verified for both the failed research run and retained-default run. Source archive integrity passed and the original live pointer is unchanged.

## Interpretation: why retain persistence? (14 November 2026)

The latest reviewed publication, `outputs/research/runs/20261114T063542Z-4aae3738`, selects persistence with MAE0.072351, RMSE0.115787 and skill0.0 over1,161 observed cell-weeks. Skill is zero by definition when the active predictor equals its reference baseline; it does not mean zero error or establish an irreducible error floor. The expanded candidates did not establish an improvement under the documented experimental protocol.

1. **Short horizon.** Predicting next week as this week is a strong low-complexity baseline when vegetation changes gradually. It can be viewed as a prior expectation of small change, but this implementation is not an explicit Bayesian model. It has no fitted-parameter estimation variance; observations and forecast errors still have variance. The proposed biological delta0.02-0.04 is a domain hypothesis, not a measured biological range here. Several evaluated weeks have observed persistence MAE near that range, but those differences include measurement and spatial-support effects. Cells have no verified wheat mask, so Punjab Rabi wheat is application context rather than confirmed crop identity. Harvest and rapid phenological transitions can violate the small-change assumption.

2. **Atmospheric contamination hypothesis.** The target week beginning22December has observed MAE0.243640 across61cells. Fog/haze escaping SCL is plausible, not a verified cause of this event. The VITO/Terrascope processing documentation describes low fog being classified as nonvegetated; our mask retains that class: [Sentinel-2 processing ATBD](https://docs.terrascope.be/DataProducts/Sentinel-2/ATBD/VITO_S2_L2A_ATBD_TOC_V220.pdf). Changing support, radiometric-offset uncertainty and actual vegetation changes are competing explanations. We have not estimated an atmospheric noise floor or proved that noise overfitting caused every candidate failure. Source imagery/reference comparisons remain required.

3. **Changing spatial support.** The30% threshold is a minimum usable-area rule, not a fixed parcel sample. Different subsets of a3km cell can contribute on successive dates. This can create apparent NDVI changes without corresponding whole-cell biological change. The cached example for B017 shows a Dec22 acquisition excluded at valid_fraction0.215778, while a Dec27 acquisition contributes the weekly value at0.609156. Equal fractions would not prove equal pixel identity either. A spatially matched support analysis is needed to quantify the effect; lower thresholds are not an automatic remedy.

4. **Limited independent history.** The942 training rows span20 shared target weeks, with correlated cells and strongly uneven weekly counts. This limits independent seasonal evidence and makes flexible-model selection unstable. It supports retaining a simpler predictor on the available evidence; it does not prove boosting can never work or define an exact effective sample size. More independently observed seasons are more valuable than merely counting more correlated rows.

**Decision:** retain persistence as the active predictor for this historical prototype. This is empirical model selection rather than forced complexity. Do not describe the asset as validated operational deployment: calibration remains provisional, field validation is absent, and the final forecast is historical. The current default selects among the stable candidate pool and chose persistence for these data; persistence is not hard-coded as the winner for every future dataset. These qualifications preserve the assignment narrative without turning plausible domain explanations into established causal findings.
