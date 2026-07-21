"""In-memory queue backend for testing and single-process mode.

Messages are stored in deque structures in memory. No persistence, no
cross-process communication. Ideal for unit tests and demo mode.
"""

import time
import threading
from collections import deque
from typing import Optional


class MemoryQueue:
    """Simple in-memory queue using deques.

    Each logical queue is a deque of (message_id, bytes) tuples.
    Consume is destructive (message is removed on read).
    """

    def __init__(self):
        self._queues: dict[str, deque] = {}
        self._locks: dict[str, threading.Lock] = {}

    def _lock(self, queue_name: str) -> threading.Lock:
        if queue_name not in self._locks:
            self._locks[queue_name] = threading.Lock()
        return self._locks[queue_name]

    def _get_queue(self, queue_name: str) -> deque:
        if queue_name not in self._queues:
            self._queues[queue_name] = deque()
        return self._queues[queue_name]

    def connect(self) -> None:
        pass

    def publish(self, queue_name: str, message: bytes) -> None:
        with self._lock(queue_name):
            q = self._get_queue(queue_name)
            q.append(message)

    def consume(self, queue_name: str, timeout: float = 1.0) -> Optional[bytes]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock(queue_name):
                q = self._get_queue(queue_name)
                if q:
                    return q.popleft()
            time.sleep(0.05)
        return None

    def acknowledge(self, queue_name: str, message_id: str) -> None:
        pass  # consume is destructive, no explicit ack needed

    def requeue(self, queue_name: str, message: bytes, delay_seconds: float = 0) -> None:
        if delay_seconds > 0:
            time.sleep(delay_seconds)
        self.publish(queue_name, message)

    def disconnect(self) -> None:
        self._queues.clear()

    def queue_length(self, queue_name: str) -> int:
        with self._lock(queue_name):
            return len(self._get_queue(queue_name))
