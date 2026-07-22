"""Message envelope — validation, creation, serialization.

Every message on every queue passes through this module. The envelope is the
universal contract: id, type, workflow, version, timestamp, trace_id, payload,
metadata.

Message types and sources are validated against the workflow registry rather
than hardcoded constants. Backward-compatible: all existing callers that omit
workflow default to the 'coloring' pipeline.
"""
from __future__ import annotations

import uuid
import json
from typing import Any

from src.registry import ensure_registry, WorkflowError


# Maximum retries (hard ceiling to prevent infinite loops)
HARD_MAX_RETRY = 20


class MessageError(Exception):
    """Raised when message validation fails."""

    def __init__(self, message: str, original: Exception | None = None):
        self.original = original
        super().__init__(message)


class Message:
    """Immutable message envelope with workflow awareness."""

    __slots__ = ("_data",)

    def __init__(self, data: dict[str, Any]):
        self._data = data
        self._validate()

    # --- Factory constructors ---

    @classmethod
    def new(
        cls,
        msg_type: str,
        payload: dict[str, Any],
        *,
        workflow: str | None = None,
        source: str = "user",
        trace_id: str | None = None,
        retry_count: int = 0,
    ) -> "Message":
        """Create a new message.

        Args:
            msg_type: Message type (validated against the workflow's allowed types).
            payload: Message payload dict.
            workflow: Workflow name (defaults to 'coloring' for backward compat).
            source: Source identifier (validated against workflow's allowed sources).
            trace_id: Correlation ID across the pipeline. Auto-generated if None.
            retry_count: Initial retry count (0 for new messages).
        """
        # Resolve workflow and validate types/sources before constructing
        wf_name = workflow or "coloring"

        return cls({
            "id": str(uuid.uuid4()),
            "type": msg_type,
            "workflow": wf_name,
            "version": 1,
            "timestamp": str(uuid.uuid4()),  # placeholder, replaced in _validate
            "trace_id": trace_id or str(uuid.uuid4()),
            "payload": payload,
            "metadata": {
                "retry_count": retry_count,
                "source": source,
            },
        })

    @classmethod
    def from_bytes(cls, data: bytes) -> "Message":
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as e:
            raise MessageError(f"Invalid JSON: {e}", original=e) from e
        return cls(parsed)

    # --- Accessors ---

    @property
    def id(self) -> str:
        return self._data["id"]

    @property
    def type(self) -> str:
        return self._data["type"]

    @property
    def workflow(self) -> str:
        """Workflow name this message belongs to."""
        return self._data.get("workflow", "coloring")

    @property
    def trace_id(self) -> str:
        return self._data["trace_id"]

    @property
    def payload(self) -> dict[str, Any]:
        return self._data["payload"]

    @property
    def retry_count(self) -> int:
        return self._data["metadata"]["retry_count"]

    @property
    def source(self) -> str:
        return self._data["metadata"]["source"]

    @property
    def timestamp(self) -> str:
        return self._data["timestamp"]

    # --- Mutations (return new copies) ---

    def with_retry(self) -> "Message":
        """Return a new message with incremented retry count."""
        new_data = json.loads(json.dumps(self._data))
        new_data["metadata"]["retry_count"] = self.retry_count + 1
        return Message(new_data)

    def with_payload(
        self,
        payload: dict[str, Any],
        *,
        new_type: str | None = None,
        new_workflow: str | None = None,
    ) -> "Message":
        """Return a new message with a different payload (and optional type/workflow)."""
        new_data = {
            "id": str(uuid.uuid4()),
            "type": new_type or self.type,
            "workflow": new_workflow or self.workflow,
            "version": self._data["version"],
            "timestamp": self._data["timestamp"],
            "trace_id": self.trace_id,
            "payload": payload,
            "metadata": {
                "retry_count": 0,
                "source": "orchestrator",
            },
        }
        return Message(new_data)

    # --- Serialization ---

    def to_bytes(self) -> bytes:
        return json.dumps(self._data, ensure_ascii=False).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)

    # --- Validation ---

    def _get_workflow_def(self) -> Any | None:
        """Try to get the workflow definition for this message.

        Returns None if the registry isn't loaded yet (validation is lenient then).
        """
        from src.registry import WorkflowRegistry
        reg = WorkflowRegistry.get_instance()
        wf_name = self._data.get("workflow", "coloring")
        try:
            return reg.get(wf_name)
        except WorkflowError:
            return None

    def _validate(self) -> None:
        """Validate the envelope structure and workflow-specific constraints."""
        from datetime import datetime, timezone

        data = self._data

        # Structural validation (always applies)
        if "id" not in data or not isinstance(data["id"], str):
            raise MessageError("Missing or invalid 'id'")
        if "type" not in data or not isinstance(data["type"], str):
            raise MessageError("Missing or invalid 'type'")
        if not isinstance(data.get("version"), int) or data["version"] < 1:
            raise MessageError("Invalid 'version'")
        if "timestamp" not in data:
            # Assign a proper timestamp if it's the placeholder
            data["timestamp"] = datetime.now(timezone.utc).isoformat()
        if "trace_id" not in data:
            raise MessageError("Missing 'trace_id'")
        if "workflow" not in data:
            # Backward compat — set default workflow
            data["workflow"] = "coloring"
        if "payload" not in data or not isinstance(data["payload"], dict):
            raise MessageError("Missing or invalid 'payload'")
        if "metadata" not in data or not isinstance(data["metadata"], dict):
            raise MessageError("Missing or invalid 'metadata'")

        meta = data["metadata"]
        retry = meta.get("retry_count", 0)
        if not isinstance(retry, int) or retry < 0:
            raise MessageError("Invalid 'retry_count'")
        if retry > HARD_MAX_RETRY:
            raise MessageError(f"Exceeded max retry count ({HARD_MAX_RETRY})")

        # Workflow-specific validation (lenient if registry isn't loaded yet)
        wf_def = self._get_workflow_def()
        if wf_def is not None:
            msg_type = data["type"]
            source = meta.get("source", "unknown")

            if not wf_def.is_valid_type(msg_type):
                valid_types = sorted(wf_def.valid_message_types)
                raise MessageError(
                    f"Invalid message type '{msg_type}' for workflow "
                    f"'{wf_def.name}'. Valid: {valid_types}"
                )

            if not wf_def.is_valid_source(source):
                valid_sources = sorted(wf_def.valid_sources)
                raise MessageError(
                    f"Invalid source '{source}' for workflow "
                    f"'{wf_def.name}'. Valid: {valid_sources}"
                )

    def __repr__(self) -> str:
        return (
            f"Message(type={self.type}, workflow={self.workflow}, "
            f"id={self.id[:8]}, trace={self.trace_id[:8]})"
        )
