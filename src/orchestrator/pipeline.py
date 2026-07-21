"""Pipeline — queue routing and orchestration loop.

The pipeline reads messages from input queues, validates them, routes them
through the state machine to the next stage, and handles errors.
"""

import logging
import signal
import time
from typing import Optional

from src.core.message import Message, MessageError
from src.core.coloring_domain import validate_request
from src.queue_backends.file_queue import FileQueue
from src.orchestrator.state_machine import StateMachine, Stage, StateMachineError
from src.orchestrator.error_handler import (
    classify_error, should_retry, get_backoff_delay, build_error_payload,
    ErrorAction,
)


logger = logging.getLogger(__name__)


class Pipeline:
    """Orchestrates the coloring page pipeline.

    Routes messages between queues according to the state machine.
    Hermes Agent runs this module as the pipeline orchestrator.
    """

    def __init__(
        self,
        queue_dir: str = ".queues/coloring",
        poll_interval: float = 0.5,
    ):
        self.queue_dir = queue_dir
        self.poll_interval = poll_interval
        self._queue = FileQueue(queue_dir)
        self._running = False
        self._shutdown_requested = False
        self._start_time: float = 0.0

        # Metrics
        self.messages_routed = 0
        self.messages_failed = 0

    def start_pipeline(self) -> None:
        """Begin the main orchestration loop."""
        self._running = True
        self._shutdown_requested = False
        self._start_time = time.monotonic()

        self._queue.connect()

        # Ensure all required queue files exist
        self._ensure_queues()

        logger.info("[pipeline] Orchestrator started. Queue dir: %s", self.queue_dir)

        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        try:
            self._run_loop()
        except Exception as e:
            logger.exception("[pipeline] Fatal error: %s", e)
        finally:
            self._cleanup()

    def _run_loop(self) -> None:
        """Main orchestration loop — reads requests, routes to reasoning."""
        while not self._shutdown_requested:
            try:
                # Process requests queue → reasoning queue (orchestrator only)
                self._process_queue("requests", Stage.REQUEST, Stage.REASONING, self._validate_and_route)

                # Monitor DLQ (just log)
                self._check_dlq()

            except Exception as e:
                logger.exception("[pipeline] Loop error: %s", e)
                time.sleep(0.5)

    def _process_queue(
        self,
        queue_name: str,
        current_stage: Stage,
        next_stage: Stage,
        handler,
    ) -> None:
        """Read one message from a queue, handle it, route to next stage."""
        raw = self._queue.consume(queue_name, timeout=self.poll_interval)
        if raw is None:
            return

        try:
            message = Message.from_bytes(raw)
        except MessageError as e:
            logger.warning("[pipeline] Invalid message on %s: %s", queue_name, e)
            self._queue.acknowledge(queue_name, "invalid")
            return

        # Route message
        self.route_message(message, queue_name, current_stage, next_stage, handler)

    def route_message(
        self,
        message: Message,
        source_queue: str,
        current_stage: Stage,
        next_stage: Stage,
        handler,
    ) -> None:
        """Route a single message through the pipeline."""
        try:
            # Apply the handler (validation, transformation)
            result = handler(message)

            if result is False:
                # Handler rejected the message
                self._send_to_dlq(message, "Message rejected by handler", "fatal_reject")
                self._queue.acknowledge(source_queue, message.id)
                self.messages_failed += 1
                return

            # Route to next queue (skip state machine if current_stage is None)
            if current_stage is not None and not StateMachine.can_transition(current_stage, next_stage):
                logger.error("[pipeline] Invalid transition %s → %s", current_stage, next_stage)
                self._send_to_dlq(message, f"Invalid transition {current_stage} → {next_stage}", "fatal_reject")
                self._queue.acknowledge(source_queue, message.id)
                self.messages_failed += 1
                return

            # Determine target queue
            if next_stage is not None:
                target_queue = StateMachine.get_queue_for_stage(next_stage)
            else:
                target_queue = "reasoning"

            # Publish to next queue
            if result is not None and isinstance(result, Message):
                self._queue.publish(target_queue, result.to_bytes())
            else:
                self._queue.publish(target_queue, message.to_bytes())

            self._queue.acknowledge(source_queue, message.id)
            self.messages_routed += 1

            logger.info(
                "[pipeline] Routed %s: %s → %s (trace=%s)",
                message.type, source_queue, target_queue, message.trace_id[:8],
            )

        except StateMachineError as e:
            self._send_to_dlq(message, str(e), "fatal_reject")
            self.messages_failed += 1
        except Exception as e:
            self._handle_routing_error(message, source_queue, e)

    def _validate_and_route(self, message: Message) -> Optional[Message]:
        """Validate a request message and route it to the reasoning stage.

        Returns the message if valid, False if rejected, or a new message
        with the transformed payload.
        """
        payload = message.payload

        try:
            validated = validate_request(
                prompt=payload.get("prompt", ""),
                age_group=payload.get("age_group", "child"),
                style=payload.get("style", "simple"),
                quantity=payload.get("quantity", 1),
            )
        except ValueError as e:
            logger.warning("[pipeline] Validation rejected: %s", e)
            return False

        # Build reasoning task payload
        reasoning_payload = {
            "request_id": message.trace_id,
            "raw_prompt": validated["prompt"],
            "age_group": validated["age_group"],
            "style": validated["style"],
            "theme": payload.get("theme", ""),
        }

        return message.with_payload(reasoning_payload, new_type="reasoning_task")

    def _route_forward(self, message: Message) -> Message:
        """Pass a message through without transformation (workers handle payloads)."""
        return message

    def _handle_routing_error(self, message: Message, source_queue: str, error: Exception) -> None:
        """Classify and handle a routing error."""
        action = classify_error(error)
        logger.warning("[pipeline] Error routing %s: %s (action=%s)", message.id[:8], error, action)

        if action == ErrorAction.RETRY and should_retry(message.retry_count):
            delay = get_backoff_delay(message.retry_count)
            retried = message.with_retry()
            self._queue.requeue(source_queue, retried.to_bytes(), delay)
        elif action == ErrorAction.DLQ or action == ErrorAction.ABORT:
            self._send_to_dlq(message, str(error), "fatal_reject")
            self._queue.acknowledge(source_queue, message.id)
        else:
            self._send_to_dlq(message, str(error), "transient")
            self._queue.acknowledge(source_queue, message.id)

        self.messages_failed += 1

    def _send_to_dlq(self, message: Message, error_msg: str, category: str) -> None:
        """Send a failed message to the DLQ."""
        dlq_payload = build_error_payload(
            request_id=message.trace_id,
            error=error_msg,
            original_message=message.to_dict(),
            retry_count=message.retry_count,
        )
        dlq_msg = Message.new("error", dlq_payload, source="orchestrator",
                              trace_id=message.trace_id)
        self._queue.publish("dlq", dlq_msg.to_bytes())
        logger.info("[pipeline] Sent to DLQ: trace=%s reason=%s", message.trace_id[:8], error_msg)

    def _check_dlq(self) -> None:
        """Check DLQ for messages (just log, don't route)."""
        count = self._queue.queue_length("dlq")
        if count > 0:
            logger.warning("[pipeline] DLQ has %d failed messages", count)

    def _ensure_queues(self) -> None:
        """Ensure all required queue files exist."""
        for name in ["requests", "reasoning", "image", "completed", "dlq",
                     "reasoning.dlq", "image.dlq"]:
            path = self._queue._file_path(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)

    def shutdown(self) -> None:
        """Request graceful shutdown."""
        self._shutdown_requested = True

    def _handle_signal(self, signum, frame) -> None:
        logger.info("[pipeline] Received signal %s, shutting down...", signum)
        self.shutdown()

    def _cleanup(self) -> None:
        self._running = False
        self._queue.disconnect()
        uptime = time.monotonic() - self._start_time
        logger.info(
            "[pipeline] Orchestrator stopped. Uptime=%.1fs Routed=%d Failed=%d",
            uptime, self.messages_routed, self.messages_failed,
        )
