"""HTTP API and browser console, using only the Python standard library."""
from __future__ import annotations

import json
import os
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from src.core import DecisionLog, Engine, ROOT, load_json

ENGINE = Engine()
DB = DecisionLog(Path(os.getenv("DATABASE_PATH", str(ROOT / "storage" / "decisions.sqlite3"))))
SAMPLES = load_json(ROOT / "data" / "validation_tickets.json")


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
        if path == "/api/health":
            return self.json(200, {"status": "ok", "documents": len(ENGINE.documents), "training_examples": len(ENGINE.examples)})
        if path == "/api/samples":
            return self.json(200, [{"ticket_id": t["ticket_id"], "subject": t["subject"] or t["body"][:70], "channel": t["channel"]} for t in SAMPLES])
        if path.startswith("/api/samples/"):
            ticket_id = path.rsplit("/", 1)[-1]
            match = next((t for t in SAMPLES if t["ticket_id"] == ticket_id), None)
            return self.json(200 if match else 404, match or {"error": "Ticket not found"})
        files = {"/": ("index.html", "text/html; charset=utf-8"), "/style.css": ("style.css", "text/css; charset=utf-8"), "/app.js": ("app.js", "application/javascript; charset=utf-8"), "/favicon.svg": ("favicon.svg", "image/svg+xml")}
        if path in files:
            name, kind = files[path]
            return self.send(200, (ROOT / "static" / name).read_bytes(), kind)
        return self.json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/triage":
            return self.json(404, {"error": "Not found"})
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
            return self.json(500, {"error": type(exc).__name__})


def main() -> None:
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"CloudServe ready at http://localhost:{port}", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
