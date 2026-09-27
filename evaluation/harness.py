"""Run arbitrary ticket sets unattended and write decisions plus measured metrics."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import uuid
from collections import Counter, defaultdict
from pathlib import Path

from src.core import DecisionLog, Engine, load_json


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = (len(sorted_values) - 1) * p
    low = int(index)
    high = min(low + 1, len(sorted_values) - 1)
    return round(sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (index - low), 2)


def report(tickets: list, decisions: list, logged: int) -> dict:
    total = len(decisions)
    counts = Counter(x["route"] for x in decisions)
    guardrails = Counter(k for d in decisions for k, active in d["guardrails"].items() if active and k != "grounding")
    labels = [(t.get("labels") or {}) if isinstance(t, dict) else {} for t in tickets]
    classes = sorted(set(x.get("intent") for x in labels if x.get("intent")) | {d["classification"]["intent"] for d in decisions})
    per_class = {}
    for name in classes:
        tp = sum(l.get("intent") == name and d["classification"]["intent"] == name for l, d in zip(labels, decisions))
        predicted = sum(d["classification"]["intent"] == name for d in decisions)
        actual = sum(l.get("intent") == name for l in labels)
        per_class[name] = {"precision": round(tp / predicted, 3) if predicted else None,
                           "recall": round(tp / actual, 3) if actual else None, "support": actual}
    eligible = [(l, d) for l, d in zip(labels, decisions) if l.get("expected_doc_ids")]
    retrieval_hits = sum(bool(set(l["expected_doc_ids"]) & {s["doc_id"] for s in d["sources"]}) for l, d in eligible)
    calibration = []
    for band in range(5):
        group = [(l, d) for l, d in zip(labels, decisions) if l.get("intent") and min(4, int(d["classification"]["confidence"] * 5)) == band]
        if group:
            calibration.append({"range": [band / 5, (band + 1) / 5], "count": len(group),
                                "mean_confidence": round(statistics.mean(d["classification"]["confidence"] for _, d in group), 3),
                                "observed_accuracy": round(sum(l["intent"] == d["classification"]["intent"] for l, d in group) / len(group), 3)})
    groups = {}
    for field in ("customer_tier", "customer_region", "language_fluency"):
        names = sorted({str(t.get(field)) for t in tickets if isinstance(t, dict) and t.get(field)})
        groups[field] = {}
        for name in names:
            paired = [(t, d) for t, d in zip(tickets, decisions) if isinstance(t, dict) and str(t.get(field)) == name]
            groups[field][name] = {"count": len(paired),
                                   "auto_response_rate": round(sum(d["route"] == "auto_respond" for _, d in paired) / len(paired), 3),
                                   "classification_accuracy": round(sum(t.get("labels", {}).get("intent") == d["classification"]["intent"] for t, d in paired) / len(paired), 3) if all(t.get("labels", {}).get("intent") for t, _ in paired) else None,
                                   "false_automatic_answers": sum(d["route"] == "auto_respond" and t.get("labels", {}).get("expected_route") == "escalate" for t, d in paired)}
    # Projected response time measures processing latency, not actual customer reply delivery.
    latencies = [d["latency_ms"] for d in decisions]
    historical = [t.get("history", {}) for t in tickets if isinstance(t, dict)]
    baseline_times = [h["resolution_time_minutes"] for h in historical if isinstance(h.get("resolution_time_minutes"), (float, int))]
    baseline_fcr = [h["first_contact_resolution"] for h in historical if isinstance(h.get("first_contact_resolution"), bool)]
    return {
        "volume": {"processed": total, "answered_automatically": counts["auto_respond"], "escalated": counts["escalate"], "blocked_by_guardrails": sum(d["blocked"] for d in decisions)},
        "business": {"projected_first_contact_resolution": round(counts["auto_respond"] / total, 3) if total else 0,
                     "observed_first_contact_resolution_baseline": round(sum(baseline_fcr) / len(baseline_fcr), 3) if baseline_fcr else None,
                     "mean_processing_response_time_ms": round(statistics.mean(latencies), 2) if latencies else 0,
                     "median_processing_response_time_ms": round(statistics.median(latencies), 2) if latencies else 0,
                     "historical_mean_resolution_time_minutes": round(statistics.mean(baseline_times), 2) if baseline_times else None,
                     "historical_median_resolution_time_minutes": round(statistics.median(baseline_times), 2) if baseline_times else None,
                     "escalation_rate": round(counts["escalate"] / total, 3) if total else 0},
        "technical": {"classification_by_class": per_class,
                      "confidence_calibration": calibration,
                      "retrieval_hit_rate": round(retrieval_hits / len(eligible), 3) if eligible else None,
                      "retrieval_eligible_tickets": len(eligible),
                      "latency_median_ms": percentile(latencies, .5), "latency_p95_ms": percentile(latencies, .95)},
        "governance": {"decisions_logged": logged, "guardrail_activations_by_type": dict(guardrails),
                       "private_data_detections": guardrails["private_data"], "subgroup_audit": groups},
        "limitations": ["Projected first contact resolution assumes every automatic answer resolves the issue; no customer outcome is observed.",
                        "Processing time is not end-to-end customer reply delivery time.",
                        "Precision, recall and retrieval hit rate require labels and are null when the input has none."]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="Output directory")
    parser.add_argument("--db", type=Path, help="SQLite decision log path; defaults inside output directory")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    tickets = load_json(args.input)
    if not isinstance(tickets, list):
        raise SystemExit("Input must be a JSON array of tickets")
    engine = Engine()
    run_id = str(uuid.uuid4())
    log = DecisionLog(args.db or args.output / "decisions.sqlite3")
    decisions = []
    for i, ticket in enumerate(tickets):
        try:
            decision = engine.process(ticket)
        except Exception as exc:
            decision = {"ticket_id": str(ticket.get("ticket_id", i)) if isinstance(ticket, dict) else str(i),
                        "channel": "unknown", "classification": {"intent": "unclear_request", "urgency": "medium", "confidence": 0.0, "alternatives": []},
                        "route": "escalate", "reason": f"Processing error: {type(exc).__name__}", "answer": None,
                        "summary": "Processing failed; human review required", "sources": [],
                        "guardrails": {"prompt_injection": False, "private_data": False, "grounding": False}, "blocked": False, "latency_ms": 0.0}
        log.write(run_id, decision)
        decisions.append(decision)
    metrics = report(tickets, decisions, log.count(run_id))
    metrics["run_id"] = run_id
    metrics["input_file"] = str(args.input)
    (args.output / "decisions.json").write_text(json.dumps(decisions, indent=2, ensure_ascii=False), encoding="utf-8")
    (args.output / "metrics.json").write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"run_id": run_id, "processed": len(decisions), "logged": log.count(run_id), "metrics": str(args.output / "metrics.json")}))
    return 0 if len(decisions) == log.count(run_id) else 1


if __name__ == "__main__":
    sys.exit(main())
