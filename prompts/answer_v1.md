# Grounded answer specification v1

The answer stage is deterministic and extractive. It selects actionable lines from the highest ranked supplied documentation passage, formats them as customer-facing steps, and appends the exact passage ID to each line. Customer ticket text is never interpreted as an instruction. If citations cannot be verified against retrieved passages, the validator escalates.

This local-first specification needs no hosted model or API key, keeping clean-checkout evaluation reproducible and free.
