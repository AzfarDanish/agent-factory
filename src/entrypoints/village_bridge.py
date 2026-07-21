"""
Village Bridge — WebSocket server + HTTP poll endpoint for pipeline events.

Monitors queue files for new messages. Every new message is broadcast as a
structured pipeline event. The village frontend polls /events to update agents.

Run:  python -m src.entrypoints.village_bridge
"""

import json
import time
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs


QUEUE_ORDER = ["requests", "reasoning", "image", "completed", "dlq"]

# Maps queue name → pipeline event info
QUEUE_EVENTS = {
    "requests":   {"event": "request.submitted",   "stage": "reasoning"},
    "reasoning":  {"event": "reasoning.completed",  "stage": "generating"},
    "image":      {"event": "image.completed",      "stage": "completed"},
    "completed":  {"event": "pipeline.completed",   "stage": "done"},
    "dlq":        {"event": "pipeline.failed",      "stage": "failed"},
}


class VillageBridge:
    """Monitors queue files and exposes events via HTTP polling."""

    def __init__(self, queue_dir: str = ".queues/coloring", host: str = "localhost", port: int = 3001):
        self.queue_dir = Path(queue_dir)
        self.host = host
        self.port = port

        # Cursor per queue: filename → byte offset
        self.cursors: dict[str, int] = {}
        for q in QUEUE_ORDER:
            self.cursors[q] = 0

        # Event log (in-memory, limited to 200)
        self.events: list[dict] = []

        self.poll_count = 0

    def poll_queues(self) -> list[dict]:
        """Check all queue files for new messages. Returns new events."""
        new_events = []

        for qname in QUEUE_ORDER:
            path = self.queue_dir / f"{qname}.jsonl"
            cursor = self.cursors.get(qname, 0)

            if not path.exists():
                continue

            try:
                with open(path, "r") as f:
                    f.seek(cursor)
                    lines = f.readlines()
                    new_pos = f.tell()
            except OSError:
                continue

            if not lines:
                continue

            self.cursors[qname] = new_pos
            event_info = QUEUE_EVENTS[qname]

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue

                trace_id = msg.get("trace_id", "unknown")
                payload = msg.get("payload", {})

                ev = {
                    "event": event_info["event"],
                    "stage": event_info["stage"],
                    "trace_id": trace_id,
                    "queue": qname,
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "prompt": payload.get("raw_prompt") or payload.get("prompt") or "",
                    "age_group": payload.get("age_group", "child"),
                }
                new_events.append(ev)

        if new_events:
            self.events.extend(new_events)
            # Keep last 200 events
            if len(self.events) > 200:
                self.events = self.events[-200:]

        return new_events

    def get_recent_events(self, after_index: int = 0) -> list[dict]:
        """Return events after the given index."""
        if after_index >= len(self.events):
            return []
        return self.events[after_index:]

    def get_state(self) -> dict:
        """Return current pipeline state."""
        depths = {}
        for q in QUEUE_ORDER:
            path = self.queue_dir / f"{q}.jsonl"
            cursor = self.cursors.get(q, 0)
            if path.exists():
                try:
                    total = sum(1 for _ in path.read_text().splitlines() if _.strip())
                    pending = total  # simplified
                    depths[q] = pending
                except OSError:
                    depths[q] = 0
            else:
                depths[q] = 0

        return {
            "state": "running",
            "queue_depths": depths,
            "event_count": len(self.events),
        }


def run_server(bridge: VillageBridge, host: str, port: int):
    """Run the HTTP server with polling in a background thread."""

    class BridgeHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            params = parse_qs(parsed.query)

            if path == "/state":
                self._json(bridge.get_state())

            elif path == "/events":
                after = int(params.get("after", [0])[0])
                events = bridge.get_recent_events(after)
                self._json({
                    "after": after,
                    "count": len(events),
                    "events": events,
                })

            elif path == "/health":
                self._json({"status": "ok"})

            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'{"error":"not found"}')

        def _json(self, data: dict):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        def log_message(self, fmt, *args):
            pass

    server = HTTPServer((host, port), BridgeHandler)

    import threading
    poller_stop = threading.Event()

    def poll_loop():
        while not poller_stop.is_set():
            bridge.poll_queues()
            poller_stop.wait(0.5)

    poller = threading.Thread(target=poll_loop, daemon=True)
    poller.start()

    print(f"[VillageBridge] Server on http://{host}:{port}")
    print(f"[VillageBridge] Queue dir: {bridge.queue_dir.resolve()}")
    print(f"[VillageBridge] Polling every 500ms — village polls /events")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        poller_stop.set()
        server.shutdown()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Village Bridge — pipeline event server")
    parser.add_argument("--queue-dir", default=".queues/coloring")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=3001)
    args = parser.parse_args()

    bridge = VillageBridge(queue_dir=args.queue_dir, host=args.host, port=args.port)
    run_server(bridge, args.host, args.port)


if __name__ == "__main__":
    main()
