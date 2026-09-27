# Reproducible run evidence

`validation/` contains the decisions, metrics, and SQLite log from a single unattended run over the supplied 80-ticket validation set on 27 September 2026. Reproduce it with:

```bash
python3 -m evaluation.harness --input data/validation_tickets.json --output evaluation/results
```

`schema_trial/` records a separate 120-record engineering trial assembled from development-schema records and edge cases. It checks run length and error handling. Its exact input is `schema_trial/input.json`; reproduce it with `python3 -m evaluation.harness --input evaluation/evidence/schema_trial/input.json --output evaluation/results/schema_trial`. It is **not** the hidden assessment set and cannot predict its score. Both directories contain synthetic capstone data only. Each `metrics.json` records the input path used during the original run, which may be unavailable on another machine; run identifiers also change on reproduction.

The SQLite files preserve one audit row for every decision. The JSON decision files are easier to inspect and are sufficient to reproduce the result counts. Actual customer first-contact resolution, first reply time, human-reviewed hallucination rate, satisfaction, and availability have not been observed; the metric fields say `null` where applicable.
