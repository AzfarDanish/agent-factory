"""Worker base class — lifecycle, heartbeat, graceful shutdown.

Every worker extends this base class. Workers read from one input queue,
process messages, and write to one output queue (or DLQ).
"""

import logging
import signal
import threading
import time
from abc import ABC, abstractmethod
from typing import Optional

from src.core.message import Message, MessageError
from src.queue_backends.file_queue import FileQueue


logger = logging.getLogger(__name__)


class WorkerError(Exception):
    """Base error for worker failures."""


class TransientError(WorkerError):
    """Retryable failure (rate limit, timeout, API unavailable)."""


class FatalError(WorkerError):
    """Non-retryable failure (invalid input, bad config)."""


class Worker(ABC):
    """Base class for all pipeline workers.

    Subclasses must implement:
    - process() — handle a single message
    - worker_name() — unique identifier for logging/heartbeat
    """

    def __init__(
        self,
        input_queue: str,
        output_queue: str,
        queue_dir: str = ".queues/coloring",
        poll_interval: float = 0.5,
    ):
        self.input_queue_name = input_queue
        self.output_queue_name = output_queue
        self.poll_interval = poll_interval
        self._queue = FileQueue(queue_dir)

        self._running = False
        self._shutdown_requested = False
        self._shutdown_timeout = 10.0

        # Metrics
        self.messages_processed = 0
        self.messages_failed = 0
        self.last_error: Optional[str] = None
        self._start_time: float = 0.0

    @property
    @abstractmethod
    def worker_name(self) -> str:
        """Unique name for this worker type."""

    @abstractmethod
    def process(self, message: Message) -> Optional[Message]:
        """Process a single message.

        Args:
            message: The input message from the queue.

        Returns:
            Output message to publish to the output queue, or None to skip.

        Raises:
            TransientError: Will retry.
            FatalError: Will send to DLQ.
        """

    def start(self) -> None:
        """Start the worker's processing loop."""
        self._running = True
        self._shutdown_requested = False
        self._start_time = time.monotonic()

        self._queue.connect()
        logger.info(
            "[%s] Worker started. Input=%s Output=%s",
            self.worker_name, self.input_queue_name, self.output_queue_name,
        )

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        try:
            self._run_loop()
        except Exception as e:
            logger.exception("[%s] Fatal error in main loop: %s", self.worker_name, e)
        finally:
            self._cleanup()

    def _run_loop(self) -> None:
        """Main processing loop."""
        while not self._shutdown_requested:
            try:
                raw = self._queue.consume(self.input_queue_name, timeout=self.poll_interval)
                if raw is None:
                    continue

                # Deserialize
                try:
                    message = Message.from_bytes(raw)
                except MessageError as e:
                    logger.warning("[%s] Invalid message: %s", self.worker_name, e)
                    self._queue.acknowledge(self.input_queue_name, "invalid")
                    continue

                # Process
                try:
                    result = self.process(message)
                except TransientError as e:
                    logger.warning("[%s] Transient error (retry): %s", self.worker_name, e)
                    retried = message.with_retry()
                    self._queue.requeue(self.input_queue_name, retried.to_bytes(), delay_seconds=2.0)
                    self.messages_failed += 1
                    self.last_error = str(e)
                    continue
                except FatalError as e:
                    logger.error("[%s] Fatal error (DLQ): %s", self.worker_name, e)
                    self._send_to_dlq(message, str(e), "fatal_reject")
                    self.messages_failed += 1
                    self.last_error = str(e)
                    continue

                # Publish result
                if result is not None:
                    self._queue.publish(self.output_queue_name, result.to_bytes())

                self._queue.acknowledge(self.input_queue_name, message.id)
                self.messages_processed += 1

            except Exception as e:
                logger.exception("[%s] Unexpected error: %s", self.worker_name, e)
                self.last_error = str(e)
                time.sleep(0.5)

    def shutdown(self, force: bool = False) -> None:
        """Request graceful shutdown."""
        self._shutdown_requested = True
        if force:
            self._running = False

    def _handle_signal(self, signum, frame) -> None:
        """Handle SIGINT/SIGTERM."""
        logger.info("[%s] Received signal %s, shutting down...", self.worker_name, signum)
        self.shutdown()

    def _cleanup(self) -> None:
        """Clean up resources."""
        self._running = False
        self._queue.disconnect()
        uptime = time.monotonic() - self._start_time
        logger.info(
            "[%s] Stopped. Uptime=%.1fs Processed=%d Failed=%d",
            self.worker_name, uptime, self.messages_processed, self.messages_failed,
        )

    def _send_to_dlq(self, message: Message, error_msg: str, category: str) -> None:
        """Send a failed message to the DLQ."""
        import uuid
        from datetime import datetime, timezone

        dlq_payload = {
            "request_id": message.trace_id,
            "error": {
                "code": "WORKER_ERROR",
                "message": error_msg,
                "category": category,
            },
            "trace": message.trace_id,
            "original_message": message.to_dict(),
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "retry_count": message.retry_count,
        }

        dlq_msg = Message.new("error", dlq_payload, source="orchestrator",
                              trace_id=message.trace_id)
        dlq_name = f"{self.input_queue_name}.dlq"
        self._queue.publish(dlq_name, dlq_msg.to_bytes())

    def health(self) -> dict:
        """Return worker health status."""
        uptime = time.monotonic() - self._start_time if self._start_time > 0 else 0
        status = "healthy"
        if not self._running:
            status = "down"
        elif self.last_error:
            status = "degraded"

        return {
            "worker": self.worker_name,
            "status": status,
            "uptime_seconds": uptime,
            "messages_processed": self.messages_processed,
            "messages_failed": self.messages_failed,
            "last_error": self.last_error,
        }
