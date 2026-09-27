# Validation evidence

The supplied 80 validation tickets were processed with the conservative route policy on 27 September 2026. Run `python3 -m evaluation.harness --input data/validation_tickets.json --output evaluation/results` to reproduce the machine-readable report. The hidden assessment set is unavailable and has not been used.

| Measure | Result | Measurement scope |
|---|---:|---|
| Tickets processed / logged | 80 / 80 | One unattended local run. |
| Automatic drafts / escalations | 7 / 73 | Drafts are not sent to customers by this demo. |
| False automatic routes against supplied labels | 0 / 7 | This is a validation-set check, not a guarantee for unseen tickets. |
| Cited primary document accuracy | 7 / 7 | Compared against expected document IDs on eligible automatic answers. Claim-level human review remains outstanding. |
| Intent accuracy | 80 / 80 | Development and validation share repeated wording; independent generalization is unproven. |
| Urgency accuracy | 33 / 80 | Low; this model should not be used alone to prioritize a real queue. |
| Retrieval hit rate | 90.6% | An expected article appeared anywhere in the returned passages for 53 labelled eligible tickets. |
| Processing latency, p95 | About 6 ms locally | Excludes delivery and customer response time. |
| Private data in outbound drafts | 0 | Pattern scan only; human privacy review is still required. |

The current policy deliberately escalates most tickets because development evidence does not support a safe automatic route for unseen wording or sensitive categories. This reduces the projected automatic share to 8.8%, below the business target; it does not measure actual first-contact resolution. Actual customer reply time, satisfaction, repeat contact, human-reviewed hallucination rate, claim-level citation support, and long-duration availability remain unmeasured. The capstone report needs the student's own interpretation of these results and limitations.
