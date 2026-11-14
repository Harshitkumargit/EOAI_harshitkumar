# AI-assistant disclosure

Codex, Claude, and Antigravity were used for planning and implementation support. Claude and Antigravity supplied early planning drafts. Codex reviewed the assignment and those drafts, consulted provider and library documentation, and produced the Python pipeline, catalogue, dashboard, tests, and documentation. Representative requests covered architecture, causal forecasting features, Sentinel-2 ingestion, evaluation, and packaging.

Codex revised the implementation after testing and saved-run review. Changes included past-only features, a separate final fit, transactional cache handling, shortlist-aligned evaluation, and explicit separation of synthetic demonstrations from satellite results. A later candidate study retained persistence because the validation-selected blend lost on the development replay. The development checks are recorded in `reports/validation.md`; the saved metrics come from the pipeline output.

The applicant completed the full 637-scene ingestion. The available record does not establish that the applicant personally reviewed every module, inspected source pixels independently, or verified the radiometric offset against original products. The applicant should be prepared to explain the code, configuration, measured results, and limitations in the live walkthrough. No field validation or production fitness is claimed.

Codex also audited the submission archive, expanded the experiment narrative, corrected packaging and generated-report issues, and verified saved metrics, tests, and the earlier-season candidate study from a fresh extraction. These automated checks are recorded in `reports/SUBMISSION_AUDIT.md` and are not presented as the applicant's personal checks.
