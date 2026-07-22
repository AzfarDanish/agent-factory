"""Village Bridge — HTTP event server for the AI Factory village frontend.

Monitors queue files across all active workflows. Every new message becomes
a structured pipeline event. The village frontend polls /events to animate
agents in real time.

Run:  python -m src.entrypoints.village_bridge  (or pnpm run dev:all)
"""
from __future__ import annotations

import json
import time
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv


# ── Queue-to-event mapping (per any queue name pattern) ─────────────────────

WORKFLOW_EVENT_MAP: dict[str, dict] = {
    # Coloring workflow
    "requests":      {"event": "request.submitted",   "stage": "reasoning"},
    "reasoning":     {"event": "reasoning.completed",  "stage": "generating"},
    "image":         {"event": "image.completed",      "stage": "completed"},
    "completed":     {"event": "pipeline.completed",   "stage": "done"},
    # Research workflow
    "research.requests":  {"event": "research.request.submitted",  "stage": "research"},
    "research.tasks":     {"event": "research.completed",          "stage": "synthesize"},
    "research.synthesis": {"event": "synthesis.completed",         "stage": "deliver"},
    "research.completed": {"event": "research.pipeline.completed", "stage": "done"},
    # Documentation workflow
    "doc.requests":  {"event": "doc.request.submitted", "stage": "outline"},
    "doc.outline":   {"event": "doc.outline.completed",  "stage": "write"},
    "doc.write":     {"event": "doc.writing.completed",  "stage": "completed"},
    "doc.completed": {"event": "doc.pipeline.completed", "stage": "done"},
}


def _detect_workflow(queue_name: str) -> str:
    """Derive workflow name from queue name prefix."""
    if queue_name.startswith("research."):
        return "research"
    if queue_name.startswith("doc."):
        return "documentation"
    return "coloring"


class VillageBridge:
    """Monitors queue files and exposes events via HTTP polling."""

    def __init__(
        self,
        queue_dir: str = ".queues/coloring",
        host: str = "localhost",
        port: int = 3001,
    ):
        self.queue_dir = Path(queue_dir)
        self.host = host
        self.port = port

        # All known queue names (coloring + research + doc)
        self.all_queues: list[str] = list(WORKFLOW_EVENT_MAP.keys())

        # Cursor per queue: filename → byte offset
        self.cursors: dict[str, int] = {}
        for q in self.all_queues:
            self.cursors[q] = 0

        # Event log (in-memory, limited to 200)
        self.events: list[dict] = []

        # Error log (in-memory, limited to 100)
        self.errors: list[dict] = []

        self.poll_count = 0
        self.health_check_count = 0

        self._check_api_keys()

    # ── Queue polling ─────────────────────────────────────────────────────

    def poll_queues(self) -> list[dict]:
        """Check all queue files for new messages. Returns new events."""
        new_events = []

        for qname in self.all_queues:
            path = self.queue_dir / f"{qname}.jsonl"
            cursor = self.cursors.get(qname, 0)

            if not path.exists():
                continue

            try:
                size = path.stat().st_size
                if size > 10_000_000:
                    self.add_error(
                        "queue_size_warning",
                        f"Queue {qname} is large ({size // 1024 // 1024}MB)",
                        f"size_bytes={size}",
                        stage="system",
                    )
                with open(path, "r") as f:
                    f.seek(cursor)
                    lines = f.readlines()
                    new_pos = f.tell()
            except OSError as e:
                self.add_error("file_error", f"Failed to read queue: {qname}", f"OSError: {e}", stage="system")
                continue

            if not lines:
                continue

            self.cursors[qname] = new_pos

            # Determine if this is an error queue
            is_dlq = qname == "dlq" or qname.endswith(".dlq")
            # Non-DLQ queues get event mapping
            event_info = WORKFLOW_EVENT_MAP.get(qname)

            for line_num, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue

                try:
                    msg = json.loads(line)
                    trace_id = msg.get("trace_id", "unknown")
                    payload = msg.get("payload", {})
                    workflow = msg.get("workflow", _detect_workflow(qname))

                    # DLQ messages are errors
                    if is_dlq:
                        error_info = payload.get("error", {})
                        err_msg = error_info.get("message", payload.get("error", "Unknown pipeline error"))
                        err_type = error_info.get("code", "pipeline_error")
                        self.add_error(
                            "pipeline_error",
                            f"Pipeline failure: {err_msg[:80]}",
                            f"trace={trace_id} type={err_type}",
                            agent=msg.get("source", ""),
                            stage="pipeline",
                        )

                    # Build event (skip DLQ queues for regular events)
                    if event_info and not is_dlq:
                        ev = {
                            "event": event_info["event"],
                            "stage": event_info["stage"],
                            "workflow": workflow,
                            "trace_id": trace_id,
                            "queue": qname,
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                            "prompt": (
                                payload.get("raw_prompt")
                                or payload.get("query")
                                or payload.get("topic")
                                or payload.get("prompt")
                                or ""
                            ),
                            "age_group": payload.get("age_group", ""),
                        }
                        new_events.append(ev)

                except json.JSONDecodeError as e:
                    self.add_error(
                        "json_decode_error",
                        f"Invalid JSON in queue: {qname}",
                        f"Line {line_num}: {e}",
                        stage="queue_processing",
                    )
                except Exception as e:
                    self.add_error(
                        "processing_error",
                        f"Error processing queue message: {qname}",
                        f"Exception: {e}",
                        stage="queue_processing",
                    )

        if new_events:
            self.events.extend(new_events)
            if len(self.events) > 200:
                self.events = self.events[-200:]

        return new_events

    # ── Event / error accessors ───────────────────────────────────────────

    def get_recent_events(self, after_index: int = 0) -> list[dict]:
        if after_index >= len(self.events):
            return []
        return self.events[after_index:]

    def get_errors(self) -> list[dict]:
        return self.errors[-50:]

    def add_error(self, error_type: str, message: str, details: str = "", agent: str = "", stage: str = ""):
        # Deduplicate: skip if last error with same type+message is < 5 seconds old
        if self.errors and self.errors[-1]["type"] == error_type and self.errors[-1]["message"] == message:
            last_ts = self.errors[-1]["timestamp"]
            try:
                last_sec = float(last_ts.split("T")[1].rstrip("Z").split(":")[2])
                now_sec = float(time.strftime("%S", time.gmtime()))
                if abs(now_sec - last_sec) < 5:
                    return
            except (ValueError, IndexError):
                pass
        error = {
            "type": error_type,
            "message": message,
            "details": details,
            "agent": agent,
            "stage": stage,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "trace_id": details.split("trace_")[-1].split(" ")[0] if "trace_" in details else "unknown",
        }
        self.errors.append(error)
        if len(self.errors) > 200:
            self.errors = self.errors[-200:]

    def _check_api_keys(self):
        deepseek = os.environ.get("FACTORY_DEEPSEEK_API_KEY", "")
        openai = os.environ.get("FACTORY_OPENAI_API_KEY", "")
        if not deepseek:
            self.add_error(
                "config_warning",
                "DeepSeek API key not set — workers use templates",
                "Set FACTORY_DEEPSEEK_API_KEY in deploy/env/.env",
                stage="system",
            )

    def get_state(self) -> dict:
        """Return current pipeline state with queue depths."""
        depths = {}
        for qname in self.all_queues:
            path = self.queue_dir / f"{qname}.jsonl"
            if path.exists():
                try:
                    total = sum(1 for _ in path.read_text().splitlines() if _.strip())
                    depths[qname] = total
                except OSError:
                    depths[qname] = 0
            else:
                depths[qname] = 0

        # Group depths by workflow
        by_workflow: dict[str, dict] = {}
        for qname, depth in depths.items():
            wf = _detect_workflow(qname)
            by_workflow.setdefault(wf, {})[qname] = depth

        return {
            "state": "running",
            "queue_depths": depths,
            "by_workflow": by_workflow,
            "event_count": len(self.events),
            "error_count": len(self.errors),
        }


# ── HTTP Server ──────────────────────────────────────────────────────────────


def run_server(bridge: VillageBridge, host: str, port: int):
    class BridgeHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            params = parse_qs(parsed.query)

            if path == "/state":
                self._json(bridge.get_state())
            elif path == "/events":
                after = int(params.get("after", ["0"])[0])
                events = bridge.get_recent_events(after)
                self._json({"after": after, "count": len(events), "events": events})
            elif path == "/errors":
                limit = int(params.get("limit", ["50"])[0])
                self._json({"count": len(bridge.errors), "errors": bridge.errors[:limit]})
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
            bridge.health_check_count += 1
            poller_stop.wait(0.5)

    poller = threading.Thread(target=poll_loop, daemon=True)
    poller.start()

    print(f"[VillageBridge] Server on http://{host}:{port}")
    print(f"[VillageBridge] Queue dir: {bridge.queue_dir.resolve()}")
    print(f"[VillageBridge] Monitoring {len(bridge.all_queues)} queues across 3 workflows")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        poller_stop.set()
        server.shutdown()


def main():
    import argparse
    env_path = Path(__file__).resolve().parent.parent.parent / "deploy" / "env" / ".env"
    load_dotenv(env_path)

    parser = argparse.ArgumentParser(description="Village Bridge — pipeline event server")
    parser.add_argument("--queue-dir", default=".queues/coloring")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=3001)
    args = parser.parse_args()

    bridge = VillageBridge(queue_dir=args.queue_dir, host=args.host, port=args.port)
    run_server(bridge, args.host, args.port)


if __name__ == "__main__":
    main()
