"""Workflow state machine — manages pipeline stage transitions.

The orchestrator uses this state machine to track the lifecycle of each
coloring request as it moves through the pipeline.
"""

from enum import Enum
from typing import Optional


class Stage(str, Enum):
    """All possible stages in the coloring page pipeline."""
    REQUEST = "request"
    REASONING = "reasoning"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


# Valid stage transitions
_TRANSITIONS: dict[Stage, list[Stage]] = {
    Stage.REQUEST: [Stage.REASONING, Stage.FAILED],
    Stage.REASONING: [Stage.GENERATING, Stage.FAILED],
    Stage.GENERATING: [Stage.COMPLETED, Stage.FAILED],
    Stage.COMPLETED: [],
    Stage.FAILED: [],
}

# Which queue each stage reads from
_STAGE_QUEUES: dict[Stage, str] = {
    Stage.REQUEST: "requests",
    Stage.REASONING: "reasoning",
    Stage.GENERATING: "image",
    Stage.COMPLETED: "completed",
}

# Message types per stage
_STAGE_MESSAGE_TYPES: dict[Stage, str] = {
    Stage.REQUEST: "request",
    Stage.REASONING: "reasoning_task",
    Stage.GENERATING: "image_task",
    Stage.COMPLETED: "result",
}


class StateMachineError(Exception):
    """Raised on invalid state transitions."""


class StateMachine:
    """Manages workflow stage transitions for the coloring pipeline."""

    @staticmethod
    def can_transition(current: Stage, target: Stage) -> bool:
        """Check if a transition from current to target is valid."""
        return target in _TRANSITIONS.get(current, [])

    @staticmethod
    def transition(current: Stage, target: Stage) -> Stage:
        """Attempt a state transition. Raises on invalid transition."""
        if not StateMachine.can_transition(current, target):
            raise StateMachineError(
                f"Cannot transition from {current.value} to {target.value}"
            )
        return target

    @staticmethod
    def get_queue_for_stage(stage: Stage) -> str:
        """Return the queue name associated with a pipeline stage."""
        return _STAGE_QUEUES.get(stage, "dlq")

    @staticmethod
    def get_message_type_for_stage(stage: Stage) -> str:
        """Return the message type associated with a pipeline stage."""
        return _STAGE_MESSAGE_TYPES.get(stage, "error")

    @staticmethod
    def max_retries() -> int:
        """Maximum retries before a message goes to DLQ."""
        return 3

    @staticmethod
    def is_terminal(stage: Stage) -> bool:
        """Check if a stage is terminal (no further transitions)."""
        return len(_TRANSITIONS.get(stage, [])) == 0
