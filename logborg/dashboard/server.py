from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from logborg.execution_state import LIVE
from logborg.runtime_orchestrator import recover


ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).resolve().parent / "static"


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path

        if path == "/":
            body = (STATIC / "index.html").read_bytes()
            self._send(200, "text/html; charset=utf-8", body)
            return

        if path == "/app.js":
            body = (STATIC / "app.js").read_bytes()
            self._send(200, "application/javascript; charset=utf-8", body)
            return

        if path == "/style.css":
            body = (STATIC / "style.css").read_bytes()
            self._send(200, "text/css; charset=utf-8", body)
            return

        if path == "/api/state":
            body = json.dumps(LIVE.snapshot()).encode()
            self._send(200, "application/json; charset=utf-8", body)
            return

        if path == "/api/events":
            self._sse()
            return

        if path == "/api/incidents":
            incidents_dir = ROOT / "incidents"
            incidents = []

            if incidents_dir.exists():
                for incident_dir in sorted(incidents_dir.iterdir(), reverse=True):
                    if not incident_dir.is_dir():
                        continue

                    manifest = incident_dir / "manifest.json"
                    evidence = incident_dir / "evidence.json"

                    item = {
                        "run_id": incident_dir.name,
                        "manifest": None,
                        "evidence": None,
                    }

                    if manifest.exists():
                        item["manifest"] = json.loads(
                            manifest.read_text(encoding="utf-8")
                        )

                    if evidence.exists():
                        item["evidence"] = json.loads(
                            evidence.read_text(encoding="utf-8")
                        )

                    incidents.append(item)

            body = json.dumps(incidents).encode()
            self._send(200, "application/json; charset=utf-8", body)
            return

        self._send(404, "text/plain; charset=utf-8", b"Not found")

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/recover":
            self._send(404, "text/plain; charset=utf-8", b"Not found")
            return

        source = ROOT / "fixtures" / "runtime_failure.py"

        def worker() -> None:
            recover(str(source), ROOT, reset_sandbox=True)

        threading.Thread(target=worker, daemon=True).start()
        self._send(202, "application/json; charset=utf-8", b'{"started":true}')

    def _sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        event = json.dumps(LIVE.snapshot())
        self.wfile.write(f"data: {event}\n\n".encode())
        self.wfile.flush()

        done = threading.Event()

        def listener(snapshot: dict) -> None:
            try:
                payload = json.dumps(snapshot)
                self.wfile.write(f"data: {payload}\n\n".encode())
                self.wfile.flush()
            except Exception:
                done.set()

        unsubscribe = LIVE.subscribe(listener)
        try:
            done.wait()
        finally:
            unsubscribe()

    def log_message(self, *_args) -> None:
        pass


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8787), Handler)
    print("LOGBORG DASHBOARD: http://127.0.0.1:8787")
    server.serve_forever()


if __name__ == "__main__":
    main()
