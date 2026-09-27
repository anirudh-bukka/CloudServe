"""Deterministic, offline support triage. Customer text is always untrusted data."""
from __future__ import annotations

import json
import hashlib
import math
import os
import re
import sqlite3
import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CHANNELS = {"email", "chat", "docs_comment", "forum"}
POLICY_INTENTS = {"security_incident", "compliance_request", "feature_request", "unclear_request"}
SENSITIVE_INTENTS = {"billing_query", "quota_or_overage", "data_residency", "api_key_issue", "database_issue"}
INJECTION = re.compile(r"(?i)(ignore (all |your |previous )?(instructions|rules)|system prompt|developer message|you are now|disregard (the |all )?(policy|instructions)|override (the |your )?(policy|rules)|do not cite|reveal (your |the )?(prompt|secrets))")
PII = re.compile(r"(?i)\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b|\b(?:\d[ -]*?){13,16}\b|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:sk|pk)_(?:live|test)_[A-Za-z0-9]{12,}\b")
TOKEN = re.compile(r"[a-z0-9]+")


def words(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def vector(text: str) -> Counter[str]:
    w = words(text)
    return Counter(w + [w[i] + "_" + w[i + 1] for i in range(len(w) - 1)])


def similarity(a: Counter[str], b: Counter[str], idf: dict[str, float]) -> float:
    shared = a.keys() & b.keys()
    dot = sum(a[x] * b[x] * idf.get(x, 1) ** 2 for x in shared)
    na = math.sqrt(sum((n * idf.get(x, 1)) ** 2 for x, n in a.items()))
    nb = math.sqrt(sum((n * idf.get(x, 1)) ** 2 for x, n in b.items()))
    return dot / (na * nb) if na and nb else 0.0


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {"body": str(raw)}
    subject = str(raw.get("subject") or "")[:1000]
    body = str(raw.get("body") or "")[:12000]
    channel = str(raw.get("channel") or "unknown").lower().strip()
    return {
        "ticket_id": str(raw.get("ticket_id") or "unidentified")[:100],
        "channel": channel if channel in CHANNELS else "unknown",
        "subject": subject, "body": body,
        "text": (subject + "\n" + body).strip(),
        "customer_tier": str(raw.get("customer_tier") or "unknown"),
        "received_at": str(raw.get("received_at") or ""),
    }


@dataclass
class Passage:
    doc_id: str
    title: str
    passage_id: str
    text: str
    score: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return vars(self).copy()


class Engine:
    def __init__(self, data_dir: Path | None = None):
        data_dir = data_dir or ROOT / "data"
        self.documents = load_json(data_dir / "documentation.json")
        training = load_json(data_dir / "development_tickets.json")
        self.examples = []
        grouped_examples = defaultdict(list)
        self.route_evidence = defaultdict(set)
        for t in training:
            n = normalize(t)
            if n["text"]:
                item = (vector(n["text"]), t["labels"]["intent"], t["labels"]["urgency"])
                self.examples.append(item)
                grouped_examples[n["text"].lower()].append(item)
                self.route_evidence[n["text"].lower()].add(t["labels"]["expected_route"])
        self.passages = []
        for doc in self.documents:
            # Headings delimit passages; each remains directly traceable to its article.
            chunks = re.split(r"(?=^## )", doc["content"], flags=re.MULTILINE)
            for i, chunk in enumerate(chunks):
                if chunk.strip():
                    self.passages.append(Passage(doc["doc_id"], doc["title"], f"{doc['doc_id']}#p{i+1}", chunk.strip()))
        all_vectors = [v for v, _, _ in self.examples] + [vector(p.title + " " + p.text) for p in self.passages]
        df = Counter(x for v in all_vectors for x in v)
        self.idf = {x: math.log((len(all_vectors) + 1) / (n + 1)) + 1 for x, n in df.items()}
        self.passage_vectors = [vector(p.title + " " + p.text) for p in self.passages]
        # Hold out complete text groups, so duplicates cannot make calibration look perfect.
        train, held_out = [], []
        for text, items in grouped_examples.items():
            bucket = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16) % 5
            (held_out if bucket == 0 else train).extend(items)
        bins = [[] for _ in range(5)]
        if train and held_out:
            for vec, truth, _ in held_out:
                predicted = self._classify_vector(vec, train)
                band = min(4, int(predicted["confidence"] * 5))
                bins[band].append(int(predicted["intent"] == truth))
        self.calibration = []
        for outcomes in bins:
            # Shrink tiny bands toward their center rather than claiming certainty.
            center = (len(self.calibration) + .5) / 5
            self.calibration.append((sum(outcomes) + 4 * center) / (len(outcomes) + 4))
        for i in range(1, 5):
            self.calibration[i] = max(self.calibration[i], self.calibration[i - 1])

    def classify(self, text: str) -> dict[str, Any]:
        if not words(text):
            return {"intent": "unclear_request", "urgency": "medium", "confidence": 0.0, "alternatives": []}
        result = self._classify_vector(vector(text), self.examples)
        band = min(4, int(result["confidence"] * 5))
        result["confidence"] = round(self.calibration[band], 3)
        return result

    def _classify_vector(self, q: Counter[str], examples: list) -> dict[str, Any]:
        matches = sorted(((similarity(q, v, self.idf), intent, urgency) for v, intent, urgency in examples), reverse=True)[:7]
        votes = defaultdict(float)
        urgency_votes = defaultdict(float)
        for score, intent, urgency in matches:
            votes[intent] += score ** 3
            urgency_votes[urgency] += score ** 3
        ranked = sorted(votes.items(), key=lambda x: (-x[1], x[0]))
        intent = ranked[0][0] if ranked else "unclear_request"
        nearest = matches[0][0] if matches else 0.0
        agreement = ranked[0][1] / max(sum(votes.values()), 1e-9) if ranked else 0.0
        confidence = round(min(0.99, max(0.0, nearest * 0.65 + agreement * 0.35)), 3)
        urgency = max(urgency_votes, key=urgency_votes.get) if urgency_votes else "medium"
        if any(x in q for x in ("outage", "breach", "compromised", "exposed", "urgent")):
            urgency = "high"
        return {"intent": intent, "urgency": urgency, "confidence": confidence,
                "alternatives": [{"intent": k, "score": round(v / max(sum(votes.values()), 1e-9), 3)} for k, v in ranked[1:4]]}

    def retrieve(self, text: str, limit: int = 4) -> list[Passage]:
        q = vector(text)
        ranked = sorted(((similarity(q, v, self.idf), p) for p, v in zip(self.passages, self.passage_vectors)), key=lambda x: -x[0])
        return [Passage(p.doc_id, p.title, p.passage_id, p.text, round(score, 3)) for score, p in ranked[:limit] if score >= 0.075]

    def _draft(self, sources: list[Passage]) -> str:
        # Extractive generation: no model can invent a claim or a source ID.
        source = sources[0]
        lines = [x.strip() for x in source.text.splitlines() if x.strip()]
        actionable = [x for x in lines if re.match(r"^(?:\d+\.|[-*])\s", x)]
        selected = actionable[:3] or [x for x in lines if not x.startswith("#")][:3]
        selected = [re.sub(r"^(?:\d+\.|[-*])\s*", "", x).strip() for x in selected]
        return "Automated draft based on the CloudServe support guide. Please verify these steps before acting:\n\n" + "\n".join(f"- {x} [{source.passage_id}]" for x in selected)

    def process(self, raw: Any) -> dict[str, Any]:
        started = time.perf_counter()
        ticket = normalize(raw)
        classification = self.classify(ticket["text"])
        sources = self.retrieve(ticket["text"])
        checks = {"prompt_injection": bool(INJECTION.search(ticket["text"])), "private_data": bool(PII.search(ticket["text"])), "grounding": False}
        reason = ""
        threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.62"))
        if os.getenv("AUTO_RESPONSE_ENABLED", "true").lower() != "true":
            reason = "Automation paused by operator kill switch"
        elif checks["prompt_injection"]:
            reason = "Customer text contains instructions aimed at the system"
        elif checks["private_data"]:
            reason = "Private data requires human review"
        elif not ticket["text"]:
            reason = "Ticket contains no question or description"
        elif classification["intent"] in POLICY_INTENTS:
            reason = "Policy requires a human for this request category"
        elif len(self.route_evidence[ticket["text"].lower()]) > 1:
            reason = "Similar historical tickets required different routes; a human should resolve the ambiguity"
        elif not sources:
            reason = "No documentation passage met the relevance floor"
        elif classification["confidence"] < (0.85 if classification["intent"] in SENSITIVE_INTENTS else threshold):
            reason = "Classification confidence is below the routing threshold"
        answer = None
        if not reason:
            answer = self._draft(sources)
            citations = re.findall(r"\[(DOC-[A-Z]+-\d+#p\d+)\]", answer)
            checks["grounding"] = bool(citations) and all(c in {s.passage_id for s in sources} for c in citations)
            if not checks["grounding"] or PII.search(answer):
                reason = "Draft failed grounding or private data validation"
                answer = None
        else:
            checks["grounding"] = bool(sources)
        route = "escalate" if reason else "auto_respond"
        return {"ticket_id": ticket["ticket_id"], "channel": ticket["channel"], "classification": classification,
                "route": route, "reason": reason or "Relevant documentation and safety checks passed",
                "answer": answer, "summary": PII.sub("[REDACTED]", ticket["text"][:280]), "sources": [s.as_dict() for s in sources],
                "guardrails": checks, "blocked": checks["prompt_injection"] or checks["private_data"] or reason == "Draft failed grounding or private data validation",
                "latency_ms": round((time.perf_counter() - started) * 1000, 2)}


class DecisionLog:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()
        self.connection.execute("CREATE TABLE IF NOT EXISTS decisions (id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, ticket_id TEXT NOT NULL, at TEXT DEFAULT CURRENT_TIMESTAMP, route TEXT NOT NULL, intent TEXT NOT NULL, confidence REAL NOT NULL, reason TEXT NOT NULL, payload TEXT NOT NULL)")
        self.connection.commit()

    def write(self, run_id: str, decision: dict[str, Any]) -> None:
        c = decision["classification"]
        with self.lock:
            self.connection.execute("INSERT INTO decisions (run_id,ticket_id,route,intent,confidence,reason,payload) VALUES (?,?,?,?,?,?,?)",
                                    (run_id, decision["ticket_id"], decision["route"], c["intent"], c["confidence"], decision["reason"], json.dumps(decision)))
            self.connection.commit()

    def count(self, run_id: str) -> int:
        with self.lock:
            return self.connection.execute("SELECT COUNT(*) FROM decisions WHERE run_id=?", (run_id,)).fetchone()[0]
