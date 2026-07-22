"""Pipeline — queue routing and orchestration loop.

The pipeline reads messages from input queues, validates them, routes them
through the state machine to the next stage, and handles errors.

Now workflow-aware: the pipeline loads a workflow definition that defines stages,
transitions, queues, and validation handlers. Multiple workflows can share the
same orchestrator instance.
"""
from __future__ import annotations

import logging
import signal
import time
from typing import Any, Callable, Optional

from src.core.message import Message, MessageError
from src.registry import get_workflow, WorkflowRegistry, WorkflowDefinition
from src.queue_backends.file_queue import FileQueue
from src.orchestrator.state_machine import StateMachine, StateMachineError
from src.orchestrator.error_handler import (
    classify_error, should_retry, get_backoff_delay, build_error_payload,
    ErrorAction,
)


logger = logging.getLogger(__name__)

# Type for validation/transformation handlers
StageHandler = Callable[[Message, Optional["StageRouter"]], Optional[Message]]


class StageRouter:
    """Holds per-workflow stage routing information during message processing."""

    def __init__(self, workflow: WorkflowDefinition):
        self.workflow = workflow
        self.sm = StateMachine(workflow)


class Pipeline:
    """Orchestrates message routing across workflows.

    Can handle multiple workflow types — routes by the message's ``workflow``
    field. For backward compat, defaults to the 'coloring' workflow.
    """

    def __init__(
        self,
        queue_dir: str = ".queues/coloring",
        poll_interval: float = 0.5,
        workflow: str | None = None,
        workflows: list[str] | None = None,
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

        # ── Workflow setup ────────────────────────────────────────────────
        # Ensure registry is loaded
        WorkflowRegistry.get_instance().load_all()

        # Determine active workflows
        if workflows is not None:
            self._active_workflows = list(workflows)
        else:
            self._active_workflows = [workflow or "coloring"]

        # Primary workflow (backward compat: "coloring")
        self._default_workflow_name = self._active_workflows[0]
        self._default_workflow = get_workflow(self._default_workflow_name)
        self._default_sm = StateMachine(self._default_workflow)

        # Per-workflow stage routers
        self._routers: dict[str, StageRouter] = {
            wf: StageRouter(get_workflow(wf))
            for wf in self._active_workflows
        }

        # ── Registered handlers ───────────────────────────────────────────
        # Map: (workflow_name, source_stage) → handler function
        self._handlers: dict[tuple[str, str], StageHandler] = {}

        # Register default handlers
        self.register_handler(
            "coloring", "request",
            lambda msg, router: Pipeline.coloring_validate_and_route(msg, router),
        )
        self.register_handler(
            "research", "request",
            lambda msg, router: Pipeline.research_validate_and_route(msg, router),
        )
        self.register_handler(
            "documentation", "request",
            lambda msg, router: Pipeline.documentation_validate_and_route(msg, router),
        )

    # ── Handler registration ──────────────────────────────────────────────

    def register_handler(
        self,
        workflow_name: str,
        source_stage: str,
        handler: StageHandler,
    ) -> None:
        """Register a validation/transformation handler for a workflow stage.

        The handler receives the message and a StageRouter, and returns a
        (possibly transformed) Message, or None to skip, or raises to trigger
        error handling.
        """
        self._handlers[(workflow_name, source_stage)] = handler

    def _get_handler(self, workflow_name: str, source_stage: str) -> StageHandler | None:
        """Get the registered handler for a workflow stage, or None."""
        return self._handlers.get((workflow_name, source_stage))

    def _get_router(self, workflow_name: str) -> StageRouter:
        """Get or create a StageRouter for a workflow."""
        if workflow_name not in self._routers:
            wf = get_workflow(workflow_name)
            self._routers[workflow_name] = StageRouter(wf)
        return self._routers[workflow_name]

    # ── Main lifecycle ────────────────────────────────────────────────────

    def start_pipeline(self) -> None:
        """Begin the main orchestration loop."""
        self._running = True
        self._shutdown_requested = False
        self._start_time = time.monotonic()

        self._queue.connect()

        # Ensure all required queue files exist for active workflows
        self._ensure_queues()

        logger.info(
            "[pipeline] Orchestrator started. Workflows=%s Queue dir: %s",
            self._active_workflows, self.queue_dir,
        )

        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        try:
            self._run_loop()
        except Exception as e:
            logger.exception("[pipeline] Fatal error: %s", e)
        finally:
            self._cleanup()

    def _run_loop(self) -> None:
        """Main orchestration loop — polls entry queues of all active workflows."""
        while not self._shutdown_requested:
            try:
                for wf_name in self._active_workflows:
                    self._poll_entry_queue(wf_name)
            except Exception as e:
                logger.exception("[pipeline] Loop error: %s", e)
                time.sleep(0.5)

    def _poll_entry_queue(self, wf_name: str) -> None:
        """Poll the entry queue of one workflow for new messages."""
        wf = get_workflow(wf_name)
        entry_stage = wf.stages[0]  # first stage = entry point
        entry_queue = wf.get_queue_for_stage(entry_stage)

        raw = self._queue.consume(entry_queue, timeout=self.poll_interval)
        if raw is None:
            return

        # Deserialize
        try:
            message = Message.from_bytes(raw)
        except MessageError as e:
            logger.warning("[pipeline] Invalid message on '%s': %s", entry_queue, e)
            self._queue.acknowledge(entry_queue, "invalid")
            return

        # Determine which workflow this message belongs to
        wf_name = message.workflow
        if not WorkflowRegistry.get_instance().has(wf_name):
            logger.warning(
                "[pipeline] Unknown workflow '%s' for message %s, using default '%s'",
                wf_name, message.id[:8], self._default_workflow_name,
            )
            wf_name = self._default_workflow_name

        router = self._get_router(wf_name)

        # Find the source stage from the queue name
        source_stage = self._resolve_stage(wf_name, entry_queue)
        if source_stage is None:
            logger.warning(
                "[pipeline] Unknown stage for queue '%s' in workflow '%s', skipping",
                entry_queue, wf_name,
            )
            self._queue.acknowledge(entry_queue, message.id)
            return

        # Get the next stage
        next_stage = self._determine_next_stage(wf_name, source_stage)
        if next_stage is None:
            logger.warning(
                "[pipeline] No transition from '%s' in workflow '%s'",
                source_stage, wf_name,
            )
            self._queue.acknowledge(entry_queue, message.id)
            return

        # Route with the registered handler
        self.route_message(message, entry_queue, source_stage, next_stage, router)

    def _resolve_stage(self, workflow_name: str, queue_name: str) -> str | None:
        """Resolve which stage produces/consumes a given queue."""
        wf = get_workflow(workflow_name)
        for stage, qname in wf.stage_queues.items():
            if qname == queue_name:
                return stage
        return None

    def _determine_next_stage(self, workflow_name: str, current_stage: str) -> str | None:
        """Determine the next stage after current_stage in the workflow.

        Skips stages that have workers (orchestrator doesn't process them).
        """
        wf = get_workflow(workflow_name)
        allowed = wf.transitions.get(current_stage, [])
        if not allowed or allowed[0] in ("failed",):
            return None
        return allowed[0]

    # ── Routing ───────────────────────────────────────────────────────────

    def route_message(
        self,
        message: Message,
        source_queue: str,
        current_stage: str,
        next_stage: str,
        router: StageRouter,
    ) -> None:
        """Route a single message through the pipeline."""
        try:
            # Apply the registered handler (validation, transformation)
            handler = self._get_handler(router.workflow.name, current_stage)

            if handler is not None:
                result = handler(message, router)

                if result is False or result is None:
                    # Handler rejected the message
                    self._send_to_dlq(
                        message,
                        "Message rejected by handler",
                        "fatal_reject",
                    )
                    self._queue.acknowledge(source_queue, message.id)
                    self.messages_failed += 1
                    return

                # If handler returned a new message, use it
                if isinstance(result, Message):
                    message = result
            else:
                # No handler — pass through as-is
                pass

            # Check state transition validity
            if not router.sm.can_transition(current_stage, next_stage):
                logger.error(
                    "[pipeline] Invalid transition %s → %s in workflow '%s'",
                    current_stage, next_stage, router.workflow.name,
                )
                self._send_to_dlq(
                    message,
                    f"Invalid transition {current_stage} → {next_stage}",
                    "fatal_reject",
                )
                self._queue.acknowledge(source_queue, message.id)
                self.messages_failed += 1
                return

            # Determine target queue
            target_queue = router.sm.get_queue_for_stage(next_stage)

            # Publish to next queue
            self._queue.publish(target_queue, message.to_bytes())
            self._queue.acknowledge(source_queue, message.id)
            self.messages_routed += 1

            logger.info(
                "[pipeline] Routed %s/%s: %s → %s (trace=%s)",
                router.workflow.name, message.type,
                source_queue, target_queue, message.trace_id[:8],
            )

        except StateMachineError as e:
            self._send_to_dlq(message, str(e), "fatal_reject")
            self.messages_failed += 1
        except Exception as e:
            self._handle_routing_error(message, source_queue, e)

    # ── Coloring-specific handler (backward compat) ───────────────────────

    @staticmethod
    def coloring_validate_and_route(
        message: Message,
        router: StageRouter,
    ) -> Optional[Message]:
        """Validate a coloring request and transform it for the reasoning stage.

        This is the coloring workflow's entry handler, replicating the original
        _validate_and_route logic.
        """
        from src.core.coloring_domain import validate_request

        payload = message.payload

        try:
            validated = validate_request(
                prompt=payload.get("prompt", ""),
                age_group=payload.get("age_group", "child"),
                style=payload.get("style", "simple"),
                quantity=payload.get("quantity", 1),
            )
        except ValueError as e:
            logger.warning("[pipeline] Coloring validation rejected: %s", e)
            return None  # rejected

        # Build reasoning task payload
        reasoning_payload = {
            "request_id": message.trace_id,
            "raw_prompt": validated["prompt"],
            "age_group": validated["age_group"],
            "style": validated["style"],
            "theme": payload.get("theme", ""),
        }

        return message.with_payload(reasoning_payload, new_type="reasoning_task")

    # ── Research-specific handler ─────────────────────────────────────────

    @staticmethod
    def research_validate_and_route(
        message: Message,
        router: StageRouter,
    ) -> Optional[Message]:
        """Validate a research request and route it to the research stage.

        Validates that the query is long enough and transforms the payload
        into a research_task for the ResearchWorker.
        """
        payload = message.payload
        query = payload.get("query", "").strip()

        if len(query) < 10:
            logger.warning("[pipeline] Research query too short (%d chars)", len(query))
            return None  # rejected

        research_payload = {
            "request_id": message.trace_id,
            "query": query,
            "depth": payload.get("depth", "standard"),
            "format": payload.get("format", "markdown"),
            "max_sources": payload.get("max_sources", 5),
        }

        return message.with_payload(research_payload, new_type="research_task")

    # ── Documentation-specific handler ─────────────────────────────────────

    @staticmethod
    def documentation_validate_and_route(
        message: Message,
        router: StageRouter,
    ) -> Optional[Message]:
        """Validate a documentation request and route it to the outline stage."""
        payload = message.payload
        topic = payload.get("topic", "").strip()

        if len(topic) < 5:
            logger.warning("[pipeline] Doc topic too short (%d chars)", len(topic))
            return None  # rejected

        doc_payload = {
            "request_id": message.trace_id,
            "topic": topic,
            "document_type": payload.get("document_type", "guide"),
            "format": payload.get("format", "markdown"),
            "tone": payload.get("tone", "formal"),
            "max_sections": payload.get("max_sections", 6),
            "audience": payload.get("audience", ""),
        }

        return message.with_payload(doc_payload, new_type="doc_request")

    # ── Error handling ────────────────────────────────────────────────────

    def _handle_routing_error(
        self,
        message: Message,
        source_queue: str,
        error: Exception,
    ) -> None:
        """Classify and handle a routing error."""
        action = classify_error(error)
        logger.warning(
            "[pipeline] Error routing %s: %s (action=%s)",
            message.id[:8], error, action,
        )

        if action == ErrorAction.RETRY:
            max_retries = StateMachine.for_workflow(message.workflow).max_retries()
            if message.retry_count < max_retries:
                delay = get_backoff_delay(message.retry_count)
                retried = message.with_retry()
                self._queue.requeue(source_queue, retried.to_bytes(), delay)
            else:
                self._send_to_dlq(message, str(error), "fatal_reject")
                self._queue.acknowledge(source_queue, message.id)
        elif action in (ErrorAction.DLQ, ErrorAction.ABORT):
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
        dlq_msg = Message.new(
            "error", dlq_payload,
            source="orchestrator",
            trace_id=message.trace_id,
            workflow=message.workflow,
        )
        self._queue.publish("dlq", dlq_msg.to_bytes())
        logger.info(
            "[pipeline] Sent to DLQ: trace=%s reason=%s",
            message.trace_id[:8], error_msg,
        )

    def _check_dlq(self) -> None:
        """Check DLQ for messages (just log, don't route)."""
        count = self._queue.queue_length("dlq")
        if count > 0:
            logger.warning("[pipeline] DLQ has %d failed messages", count)

    def _ensure_queues(self) -> None:
        """Ensure all required queue files exist for all active workflows."""
        seen = set()
        for wf_name in self._active_workflows:
            sm = StateMachine.for_workflow(wf_name)
            for name in sm.all_queues():
                if name not in seen:
                    seen.add(name)
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

    # ── Deprecated backward-compat methods ────────────────────────────────

    def _process_queue(self, queue_name, current_stage, next_stage, handler):
        """Legacy single-queue processing — delegates to the new system.

        Used by existing tests that call this directly.
        """
        raw = self._queue.consume(queue_name, timeout=self.poll_interval)
        if raw is None:
            return

        try:
            message = Message.from_bytes(raw)
        except MessageError as e:
            logger.warning("[pipeline] Invalid message on %s: %s", queue_name, e)
            self._queue.acknowledge(queue_name, "invalid")
            return

        router = self._get_router(message.workflow)

        # If a handler was passed directly, use it; otherwise look up registered
        if handler is not None and handler.__name__ != "_route_forward":
            result = handler(message)
            if result is False or result is None:
                self._send_to_dlq(message, "Message rejected by handler", "fatal_reject")
                self._queue.acknowledge(queue_name, message.id)
                self.messages_failed += 1
                return
            if isinstance(result, Message):
                message = result

        # Route to next queue
        if next_stage is not None:
            target_queue = router.sm.get_queue_for_stage(next_stage)
        else:
            target_queue = "reasoning"

        self._queue.publish(target_queue, message.to_bytes())
        self._queue.acknowledge(queue_name, message.id)
        self.messages_routed += 1

        logger.info(
            "[pipeline] Routed %s/%s: %s → %s (trace=%s)",
            message.workflow, message.type,
            queue_name, target_queue, message.trace_id[:8],
        )

    @staticmethod
    def _validate_and_route(message: Message) -> Optional[Message]:
        """Legacy static validation — delegates to the coloring handler.

        Kept for backward compat with tests that pass it as a callback.
        """
        return Pipeline.coloring_validate_and_route(
            message, StageRouter(get_workflow("coloring"))
        )

    @staticmethod
    def _route_forward(message: Message) -> Message:
        # No-op pass-through (kept for backward compat)
        return message
