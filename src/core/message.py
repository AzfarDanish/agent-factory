"""Message envelope — validation, creation, serialization.

Every message on every queue passes through this module. The envelope is the
universal contract: id, type, version, timestamp, trace_id, payload, metadata.
"""

import uuid
import json
from datetime import datetime, timezone
from typing import Any

# Allowed message types and their source queues
VALID_TYPES = {"request", "reasoning_task", "image_task", "result", "error"}
VALID_SOURCES = {"user", "orchestrator", "reasoning_worker", "image_worker"}

MAX_RETRY_COUNT = 5


class MessageError(Exception):
    """Raised when message validation fails."""


class Message:
    """Immutable message envelope."""

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
        source: str = "user",
        trace_id: str | None = None,
        retry_count: int = 0,
    ) -> "Message":
        if msg_type not in VALID_TYPES:
            raise MessageError(f"Invalid message type: {msg_type}")
        if source not in VALID_SOURCES:
            raise MessageError(f"Invalid source: {source}")

        return cls({
            "id": str(uuid.uuid4()),
            "type": msg_type,
            "version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
            raise MessageError(f"Invalid JSON: {e}") from e
        return cls(parsed)

    # --- Accessors ---

    @property
    def id(self) -> str:
        return self._data["id"]

    @property
    def type(self) -> str:
        return self._data["type"]

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

    def with_payload(self, payload: dict[str, Any], *, new_type: str | None = None) -> "Message":
        """Return a new message with a different payload (and optional type)."""
        new_data = {
            "id": str(uuid.uuid4()),
            "type": new_type or self.type,
            "version": self._data["version"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
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

    def _validate(self) -> None:
        data = self._data

        if "id" not in data or not isinstance(data["id"], str):
            raise MessageError("Missing or invalid 'id'")
        if data.get("type") not in VALID_TYPES:
            raise MessageError(f"Invalid or missing 'type': {data.get('type')}")
        if not isinstance(data.get("version"), int) or data["version"] < 1:
            raise MessageError("Invalid 'version'")
        if "timestamp" not in data:
            raise MessageError("Missing 'timestamp'")
        if "trace_id" not in data:
            raise MessageError("Missing 'trace_id'")
        if "payload" not in data or not isinstance(data["payload"], dict):
            raise MessageError("Missing or invalid 'payload'")
        if "metadata" not in data or not isinstance(data["metadata"], dict):
            raise MessageError("Missing or invalid 'metadata'")

        meta = data["metadata"]
        retry = meta.get("retry_count", 0)
        if not isinstance(retry, int) or retry < 0:
            raise MessageError("Invalid 'retry_count'")
        if retry > MAX_RETRY_COUNT:
            raise MessageError(f"Exceeded max retry count ({MAX_RETRY_COUNT})")

        if meta.get("source") not in VALID_SOURCES:
            raise MessageError(f"Invalid 'source': {meta.get('source')}")

    def __repr__(self) -> str:
        return f"Message(type={self.type}, id={self.id[:8]}, trace={self.trace_id[:8]})"
