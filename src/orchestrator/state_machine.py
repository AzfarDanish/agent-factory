"""Workflow state machine — manages pipeline stage transitions.

The state machine is now workflow-aware: stages, transitions, queues, and
message types are all defined per workflow in config/workflows/*.yaml.

Backward compatibility: the old `Stage` enum and `StateMachine` static methods
still work by defaulting to the 'coloring' workflow. Prefer instantiating
`StateMachine.for_workflow(name)` for new code.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from src.registry import get_workflow, WorkflowDefinition


class Stage(str, Enum):
    """Legacy stage enum — kept for backward compat with coloring pipeline.

    New code should use workflow definitions directly or instantiate
    StateMachine.for_workflow(). The values here mirror the coloring workflow.
    """
    REQUEST = "request"
    REASONING = "reasoning"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class StateMachineError(Exception):
    """Raised on invalid state transitions."""


class StateMachine:
    """Manages workflow stage transitions.

    Instantiate with a workflow definition, or use the class methods for
    backward-compatible access to the coloring workflow.
    """

    # Cache default instance for backward-compatible static access
    _default_instance: StateMachine | None = None
    _instances: dict[str, StateMachine] = {}

    def __init__(self, workflow: WorkflowDefinition):
        self._workflow = workflow

    @classmethod
    def for_workflow(cls, name: str | None = None) -> StateMachine:
        """Get or create a StateMachine for a named workflow.

        Caches per workflow name so the same definition is reused.
        """
        wf_name = name or "coloring"
        if wf_name not in cls._instances:
            wf_def = get_workflow(wf_name)
            sm = cls(wf_def)
            cls._instances[wf_name] = sm
            # If this is the coloring workflow, also set as default
            if wf_name == "coloring":
                cls._default_instance = sm
        return cls._instances[wf_name]

    @classmethod
    def _get_default(cls) -> StateMachine:
        """Get the default (coloring workflow) state machine."""
        if cls._default_instance is None:
            cls._default_instance = cls.for_workflow("coloring")
        return cls._default_instance

    # ── Instance methods ──────────────────────────────────────────────────

    @property
    def workflow(self) -> WorkflowDefinition:
        return self._workflow

    def can_transition(self, current: str, target: str) -> bool:
        """Check if a transition from current stage to target is valid."""
        return self._workflow.can_transition(current, target)

    def do_transition(self, current: str, target: str) -> str:
        """Attempt a state transition. Raises on invalid transition."""
        if not self.can_transition(current, target):
            raise StateMachineError(
                f"Cannot transition from '{current}' to '{target}' "
                f"in workflow '{self._workflow.name}'"
            )
        return target

    def get_queue_for_stage(self, stage: str) -> str:
        """Return the queue name associated with a pipeline stage."""
        q = self._workflow.get_queue_for_stage(stage)
        if not q:
            raise StateMachineError(
                f"Stage '{stage}' has no queue in workflow '{self._workflow.name}'"
            )
        return q

    def get_message_type_for_stage(self, stage: str) -> str:
        """Return the message type associated with a pipeline stage."""
        t = self._workflow.get_message_type_for_stage(stage)
        if not t:
            raise StateMachineError(
                f"Stage '{stage}' has no message type in workflow '{self._workflow.name}'"
            )
        return t

    def max_retries(self) -> int:
        return self._workflow.max_retries

    def is_terminal(self, stage: str) -> bool:
        return self._workflow.is_terminal(stage)

    def stages(self) -> list[str]:
        return list(self._workflow.stages)

    def all_queues(self) -> list[str]:
        """Return all queue names used by this workflow."""
        queues = set(self._workflow.stage_queues.values())
        queues.update(f"{q}.dlq" for q in list(queues))
        queues.add("dlq")
        return sorted(queues)

    # ── Backward-compatible static methods (delegate to coloring workflow) ─

    @staticmethod
    def static_can_transition(current: Stage, target: Stage) -> bool:
        """Legacy: check transition with Stage enum values.

        Delegates to the coloring workflow. This is a separate name to avoid
        shadowing the instance method 'can_transition'.
        """
        sm = StateMachine._get_default()
        return sm.can_transition(current.value, target.value)

    @staticmethod
    def static_get_queue_for_stage(stage: Stage) -> str:
        """Legacy: get queue name for a Stage enum value."""
        sm = StateMachine._get_default()
        return sm.get_queue_for_stage(stage.value)

    @staticmethod
    def static_get_message_type_for_stage(stage: Stage) -> str:
        """Legacy: get message type for a Stage enum value."""
        sm = StateMachine._get_default()
        return sm.get_message_type_for_stage(stage.value)

    @staticmethod
    def static_max_retries() -> int:
        """Legacy: max retries for the coloring workflow."""
        return StateMachine._get_default()._workflow.max_retries

    @staticmethod
    def static_is_terminal(stage: Stage) -> bool:
        """Legacy: check if a Stage is terminal."""
        sm = StateMachine._get_default()
        return sm.is_terminal(stage.value)
