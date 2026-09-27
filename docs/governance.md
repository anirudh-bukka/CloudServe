# Governance and incident response

## Operating boundary

This system is a capstone demonstration using synthetic CloudServe data. It should not be used for real customers without authentication, tenant isolation, durable audit storage, privacy review, rate limiting, measured answer quality, and an operator on call. Automatic replies are prepared by the system, but the demo does not send email or messages to customers.

## Decision policy

1. Creating `storage/pause_auto_responses` pauses automatic drafts on the next ticket without restarting; `AUTO_RESPONSE_ENABLED=false` is a startup control.
2. Prompt injection patterns and private data trigger human review.
3. Security incidents, compliance requests, feature requests, and unclear requests require a human.
4. Ambiguous historical routes, no relevant documentation, low confidence, unseen wording, or disagreement on the primary document require a human.
5. A drafted response is released only if every citation resolves to a retrieved passage and no private data is in the answer.

A support lead should inspect an escalation's `reason`, `summary`, `sources`, and `guardrails` before responding. The decision log records every route. If the system itself fails on a ticket, the batch harness writes an escalation so the ticket remains visible.

## Risk register

| Risk | Impact | Mitigation | Remaining gap |
|---|---|---|---|
| Unsupported answer | Misleads customer | Extractive lines and citation verification | Source article may itself be wrong or stale |
| Sensitive content in ticket | Privacy breach | Detect and redact common private data patterns; escalate | Pattern detection cannot catch every identifier |
| Prompt injection | Unsafe route or output | Treat ticket text as data and block known instruction patterns | Novel phrasing could evade regex |
| Classifier overconfidence | Wrong automatic answer | Policy classes and sensitive-class threshold, historical ambiguity escalation | Confidence is not formally calibrated |
| Missing document | Invented source | Relevance floor and escalation on no hit | Near matches can still be wrong |
| Lost logs on free hosting | Audit gap | SQLite locally, note ephemeral host storage | Production needs durable database and backup |

## Incident procedure

1. Detect by reviewing logs, reports, and user complaints. Record affected ticket IDs and times.
2. Contain by creating `storage/pause_auto_responses`; the next ticket escalates without restarting. Verify with a test ticket.
3. Assess the SQLite log and affected responses; identify whether sensitive data was exposed or unsupported guidance was sent.
4. Notify the support lead and any required privacy or security owner under the organization's policy.
5. Correct the source article, classifier, or guardrail; test the failure case and a full batch before restoring automation.
6. Document the cause, impact, actions, and follow-up owner.

## Fairness audit approach

The validation set includes region, customer tier, and language fluency. Compare automatic answer rate, classification errors, retrieval hit rate, and false automatic answers across these fields. Small subgroup counts can make apparent differences noisy; report denominators and avoid claiming equal quality from one small sample. Do not use tier, region, or fluency as classifier features. They are retained only for auditing.
