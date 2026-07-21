"""Tests for message envelope."""

import json
import pytest
from src.core.message import Message, MessageError, VALID_TYPES


class TestMessageCreation:
    def test_new_request_message(self):
        msg = Message.new("request", {"prompt": "a dragon", "age_group": "child"})
        assert msg.type == "request"
        assert msg.payload["prompt"] == "a dragon"
        assert msg.retry_count == 0
        assert msg.source == "user"
        assert len(msg.id) == 36  # uuid

    def test_new_message_with_source(self):
        msg = Message.new("reasoning_task", {}, source="orchestrator")
        assert msg.source == "orchestrator"

    def test_new_message_with_trace(self):
        msg = Message.new("request", {}, trace_id="abc-123")
        assert msg.trace_id == "abc-123"

    def test_invalid_type_raises(self):
        with pytest.raises(MessageError, match="Invalid message type"):
            Message.new("invalid_type", {})

    def test_invalid_source_raises(self):
        with pytest.raises(MessageError, match="Invalid source"):
            Message.new("request", {}, source="hacker")


class TestMessageSerialization:
    def test_roundtrip_bytes(self):
        original = Message.new("image_task", {"prompt": "test"})
        data = original.to_bytes()
        restored = Message.from_bytes(data)
        assert restored.id == original.id
        assert restored.type == original.type
        assert restored.payload == original.payload

    def test_from_bytes_invalid_json(self):
        with pytest.raises(MessageError, match="Invalid JSON"):
            Message.from_bytes(b"not json")

    def test_to_dict(self):
        msg = Message.new("request", {"key": "value"})
        d = msg.to_dict()
        assert d["type"] == "request"
        assert d["payload"]["key"] == "value"

    def test_repr(self):
        msg = Message.new("request", {})
        r = repr(msg)
        assert msg.id[:8] in r
        assert "request" in r


class TestMessageValidation:
    def test_missing_id_raises(self):
        with pytest.raises(MessageError, match="Missing or invalid 'id'"):
            Message({"type": "request", "version": 1, "timestamp": "x", "trace_id": "x",
                     "payload": {}, "metadata": {"retry_count": 0, "source": "user"}})

    def test_exceeded_retry_raises(self):
        with pytest.raises(MessageError, match="Exceeded max retry"):
            Message({"id": "x", "type": "request", "version": 1, "timestamp": "x",
                     "trace_id": "x", "payload": {},
                     "metadata": {"retry_count": 999, "source": "user"}})


class TestMessageMutations:
    def test_with_retry_increments_count(self):
        msg = Message.new("request", {})
        assert msg.retry_count == 0
        retried = msg.with_retry()
        assert retried.retry_count == 1
        assert retried.id == msg.id  # same id (retry)

    def test_with_payload_creates_new_message(self):
        msg = Message.new("request", {"raw": "data"})
        new_msg = msg.with_payload({"refined": "data"}, new_type="reasoning_task")
        assert new_msg.id != msg.id  # new message, new id
        assert new_msg.type == "reasoning_task"
        assert new_msg.payload["refined"] == "data"
        assert new_msg.source == "orchestrator"
        assert new_msg.trace_id == msg.trace_id  # same trace
