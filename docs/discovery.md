# Discovery evidence

These findings are calculated from the supplied 500 development tickets and checked against the five supplied stakeholder transcripts. They describe the fictional CloudServe operation, not live customers.

| Finding | Evidence | Design implication |
|---|---|---|
| Known answers are hard to deliver | 357 of 500 tickets (71.4%) are labelled answerable from documentation. Sofia and Ines both describe poor internal findability. | Retrieve from the reviewed knowledge base and show the passage with each answer. |
| Escalation often lacks context | 281 tickets were escalated; 138 of those (49.1%) are labelled answerable from documentation. Daniel says escalations often arrive without a summary or what was tried. | Attach classification, summary, source passages, and a plain-language reason to every escalation. |
| Documentation comments are especially weak | Of 78 documentation comments, 34.6% reached first contact resolution; median resolution time was 465.5 minutes and 33.3% had repeat contact. | Treat docs comments as a first-class input channel. |
| Customer tier assumptions are misleading | Median resolution time was 369 minutes for enterprise, 266 for standard, and 141 for business. Ravi's impression that enterprise gets answers in an hour does not match this sample. | Audit outcomes by tier rather than assuming priority works. |
| Language concerns need measurement | Mean historical satisfaction was 2.95 for fluent and 3.04 for non-fluent tickets. Sofia's concern about worst satisfaction among non-fluent customers is not supported by this sample. | Audit retrieval and routing across language groups without using fluency to penalize a ticket. |

The operational problem is that existing, reviewed answers do not reach agents and customers reliably, while the queue treats different urgency levels similarly and escalations lose context. A cited triage and retrieval workflow addresses this more directly than a free-form chatbot.

Open questions: the supplied data does not include actual time to first reply for every ticket, real post-automation satisfaction, or the cost of a wrong automatic answer. Production decisions need those measurements.
