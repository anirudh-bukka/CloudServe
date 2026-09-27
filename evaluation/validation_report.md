# Validation run and interpretation

This is an initial evaluation on the 80 supplied validation tickets. Re-run `python3 -m evaluation.harness --input data/validation_tickets.json --output evaluation/results` to regenerate the machine-readable report. The hidden assessment set is not available and has not been used.

| Measure | Result | Interpretation |
|---|---:|---|
| Tickets processed / logged | 80 / 80 | The batch gate completed without intervention and the log reconciled. |
| Automatic drafts / escalations | 53 / 27 | The projected automatic share is 66.2%; no customer outcome is observed. |
| Intent accuracy | 80 / 80 | Many validation texts repeat development patterns; this does not establish real-world generalization. |
| Retrieval hit rate | 90.6% | An expected article appeared among returned passages for labelled eligible tickets. |
| Processing latency, p95 | About 7 ms locally | This excludes network and actual delivery time. |
| Auto draft when expected route was escalation | 12 / 53 | This is a material safety gap. The supplied labels sometimes disagree on route for the same wording, so textual confidence cannot resolve all cases. Do not send these drafts to real customers automatically. |
| Private data or prompt injection blocks in the sample | 0 | Purpose-built guardrail tests do trigger each block. |

The figures above should be treated with caution because many validation tickets duplicate or closely resemble development tickets, automatic drafts were not checked by two independent human reviewers, and there is no observed post-answer resolution or satisfaction. The 66.2% automatic share must not be called a measured first contact resolution rate. A human review workflow is the appropriate next deployment step until the false automatic route issue is reduced and reviewed against a genuinely independent sample.

In the subgroup audit, automatic share is 63.9% for 61 fluent tickets and 73.7% for 19 non-fluent tickets. Seven of the 19 non-fluent tickets received automatic drafts where their labels expected escalation, compared with five of 61 fluent tickets. Small group sizes and contradictory route labels limit interpretation, but this deserves investigation before production.
