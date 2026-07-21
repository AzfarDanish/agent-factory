"""File-based queue backend using JSONL files.

Each queue is an append-only JSONL file. Messages are written as newline-delimited
JSON records. Consume reads the oldest unacknowledged message by tracking a cursor
per queue file.

Phase 1 backend — zero dependencies, suitable for development and single-machine use.
"""

import json
import os
import time
import threading
from pathlib import Path
from typing import Optional


class FileQueue:
    """JSONL file-based queue.

    Each logical queue maps to a .jsonl file. Messages are appended.
    A companion cursor file (.cursor) tracks the last-read position.

    This is NOT production-safe (no atomicity guarantees, no multi-consumer).
    It is a dev/test backend that lets us build and iterate fast.
    """

    def __init__(self, queue_dir: str | Path):
        self.queue_dir = Path(queue_dir)
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, threading.Lock] = {}
        self._cursor_cache: dict[str, int] = {}

    def _lock(self, queue_name: str) -> threading.Lock:
        if queue_name not in self._locks:
            self._locks[queue_name] = threading.Lock()
        return self._locks[queue_name]

    def _file_path(self, queue_name: str) -> Path:
        """Get the path for a queue file."""
        return self.queue_dir / f"{queue_name}.jsonl"

    def _cursor_path(self, queue_name: str) -> Path:
        """Get the path for a cursor file."""
        return self.queue_dir / f"{queue_name}.cursor"

    def connect(self) -> None:
        """Ensure queue directory exists."""
        self.queue_dir.mkdir(parents=True, exist_ok=True)

    def publish(self, queue_name: str, message: bytes) -> None:
        """Append a message to the queue file."""
        path = self._file_path(queue_name)
        with self._lock(queue_name):
            with open(path, "ab") as f:
                f.write(message + b"\n")
                f.flush()
                os.fsync(f.fileno())

    def consume(self, queue_name: str, timeout: float = 1.0) -> Optional[bytes]:
        """Read the oldest unacknowledged message.

        Uses a cursor file to track position. Returns None if the queue
        is empty within the timeout period.
        """
        path = self._file_path(queue_name)
        cursor_path = self._cursor_path(queue_name)
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            with self._lock(queue_name):
                if not path.exists():
                    time.sleep(0.1)
                    continue

                # Read cursor position
                cursor = self._read_cursor(cursor_path)

                # Read all lines
                with open(path, "r") as f:
                    f.seek(cursor)
                    lines = f.readlines()
                    new_cursor = f.tell()

                if not lines:
                    time.sleep(0.1)
                    continue

                # Return first unread line, advance cursor past it only
                first_line = lines[0].strip()
                if first_line:
                    # Advance cursor past just this one line (line includes \n)
                    advance = len(lines[0].encode("utf-8"))
                    self._write_cursor(cursor_path, cursor + advance)
                    return first_line.encode("utf-8")

        return None

    def acknowledge(self, queue_name: str, message_id: str) -> None:
        """No-op for file backend. Cursor advancement is acknowledgement."""
        pass

    def requeue(self, queue_name: str, message: bytes, delay_seconds: float = 0) -> None:
        """Re-publish a message (append to the queue again)."""
        if delay_seconds > 0:
            time.sleep(delay_seconds)
        self.publish(queue_name, message)

    def disconnect(self) -> None:
        """No-op for file backend."""
        pass

    def queue_length(self, queue_name: str) -> int:
        """Return the number of unacknowledged messages."""
        path = self._file_path(queue_name)
        cursor_path = self._cursor_path(queue_name)

        with self._lock(queue_name):
            if not path.exists():
                return 0
            cursor = self._read_cursor(cursor_path)
            with open(path, "r") as f:
                f.seek(cursor)
                return len([l for l in f.readlines() if l.strip()])

    def reset_cursor(self, queue_name: str) -> None:
        """Reset cursor to beginning (for testing)."""
        cursor_path = self._cursor_path(queue_name)
        with self._lock(queue_name):
            self._write_cursor(cursor_path, 0)

    def _read_cursor(self, path: Path) -> int:
        """Read cursor position from file."""
        if path.exists():
            with open(path, "r") as f:
                try:
                    return int(f.read().strip())
                except (ValueError, OSError):
                    return 0
        return 0

    def _write_cursor(self, path: Path, position: int) -> None:
        """Write cursor position to file."""
        with open(path, "w") as f:
            f.write(str(position))
            f.flush()
            os.fsync(f.fileno())
