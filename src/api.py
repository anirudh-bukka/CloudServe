"""HTTP API and browser console, using only the Python standard library."""
from __future__ import annotations

import json
import os
import uuid
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from src.core import DecisionLog, Engine, ROOT, failure_decision, load_json

ENGINE = Engine()
DB = DecisionLog(Path(os.getenv("DATABASE_PATH", str(ROOT / "storage" / "decisions.sqlite3"))))
SAMPLES = load_json(ROOT / "data" / "validation_tickets.json")


def metrics_text() -> bytes:
    with DB.lock:
        rows = DB.connection.execute("SELECT payload FROM decisions").fetchall()
    decisions = [json.loads(row[0]) for row in rows]
    routes = Counter((d["channel"], d["route"]) for d in decisions)
    blocks = Counter(key for d in decisions for key, active in d["guardrails"].items()
                     if active and key != "grounding")
    latencies = sorted(d["latency_ms"] / 1000 for d in decisions)
    confidences = Counter(min(4, int(d["classification"]["confidence"] * 5)) for d in decisions)
    lines = ["# HELP cloudserve_tickets_processed_total Logged tickets by channel and outcome",
             "# TYPE cloudserve_tickets_processed_total counter"]
    lines.extend(f'cloudserve_tickets_processed_total{{channel="{channel}",outcome="{outcome}"}} {count}'
                 for (channel, outcome), count in sorted(routes.items()))
    lines += ["# HELP cloudserve_guardrail_activations_total Guardrail detections",
              "# TYPE cloudserve_guardrail_activations_total counter"]
    lines.extend(f'cloudserve_guardrail_activations_total{{guardrail="{name}"}} {count}'
                 for name, count in sorted(blocks.items()))
    lines += ["# HELP cloudserve_processing_latency_seconds Processing latency quantiles",
              "# TYPE cloudserve_processing_latency_seconds gauge"]
    for label, index in (("0.5", .5), ("0.95", .95)):
        value = latencies[round((len(latencies) - 1) * index)] if latencies else 0
        lines.append(f'cloudserve_processing_latency_seconds{{quantile="{label}"}} {value:.6f}')
    lines += ["# HELP cloudserve_confidence_band_total Decisions by confidence band",
              "# TYPE cloudserve_confidence_band_total gauge"]
    lines.extend(f'cloudserve_confidence_band_total{{band="{band}"}} {confidences[band]}' for band in range(5))
    return ("\n".join(lines) + "\n").encode()


class Handler(BaseHTTPRequestHandler):
    def send(self, status: int, data: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def json(self, status: int, obj: object) -> None:
        self.send(status, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/metrics":
            try:
                return self.send(200, metrics_text(), "text/plain; version=0.0.4; charset=utf-8")
            except Exception:
                return self.json(503, {"error": "Metrics unavailable"})
        if path == "/api/health":
            try:
                with DB.lock:
                    DB.connection.execute("SELECT 1").fetchone()
                database = "ok"
            except Exception:
                database = "unavailable"
            healthy = database == "ok"
            return self.json(200 if healthy else 503, {
                "status": "ok" if healthy else "degraded",
                "documents": len(ENGINE.documents),
                "training_examples": len(ENGINE.examples),
                "database": database,
                "automation_enabled": os.getenv("AUTO_RESPONSE_ENABLED", "true").lower() == "true"
                    and not Path(os.getenv("AUTO_RESPONSE_PAUSE_FILE", str(ROOT / "storage" / "pause_auto_responses"))).exists(),
            })
        if path == "/api/samples":
            return self.json(200, [{"ticket_id": t["ticket_id"], "subject": t["subject"] or t["body"][:70], "channel": t["channel"]} for t in SAMPLES])
        if path.startswith("/api/samples/"):
            ticket_id = path.rsplit("/", 1)[-1]
            match = next((t for t in SAMPLES if t["ticket_id"] == ticket_id), None)
            return self.json(200 if match else 404, match or {"error": "Ticket not found"})
        files = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/status": ("status.html", "text/html; charset=utf-8"),
            "/style.css": ("style.css", "text/css; charset=utf-8"),
            "/app.js": ("app.js", "application/javascript; charset=utf-8"),
            "/status.js": ("status.js", "application/javascript; charset=utf-8"),
            "/favicon.svg": ("favicon.svg", "image/svg+xml"),
        }
        if path in files:
            name, kind = files[path]
            return self.send(200, (ROOT / "static" / name).read_bytes(), kind)
        return self.json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/triage":
            return self.json(404, {"error": "Not found"})
        ticket = {}
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size > 100000:
                return self.json(413, {"error": "Ticket too large"})
            ticket = json.loads(self.rfile.read(size))
            decision = ENGINE.process(ticket)
            DB.write(str(uuid.uuid4()), decision)
            return self.json(200, decision)
        except (ValueError, TypeError, json.JSONDecodeError):
            return self.json(400, {"error": "Invalid JSON ticket"})
        except Exception as exc:
            decision = failure_decision(ticket, exc)
            try:
                DB.write(str(uuid.uuid4()), decision)
            except Exception:
                return self.json(503, {"error": "Decision log unavailable; ticket requires human review"})
            return self.json(200, decision)


def main() -> None:
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"CloudServe ready at http://localhost:{port}", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
