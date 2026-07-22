"""Tests for message envelope.

NOTE: These tests require the workflow registry to be loaded (at least the
'coloring' workflow) so that type and source validation works correctly.
"""
from __future__ import annotations

import json
import pytest
from src.core.message import Message, MessageError

# Ensure the workflow registry is loaded (seeds the 'coloring' workflow)
from src.registry import ensure_registry
ensure_registry()


class TestMessageCreation:
    def test_new_request_message(self):
        msg = Message.new("request", {"prompt": "a dragon", "age_group": "child"})
        assert msg.type == "request"
        assert msg.workflow == "coloring"
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

    def test_new_message_with_workflow(self):
        msg = Message.new("request", {}, workflow="coloring")
        assert msg.workflow == "coloring"

    def test_invalid_type_raises(self):
        with pytest.raises(MessageError, match="Invalid message type"):
            Message.new("invalid_type", {})

    def test_invalid_source_raises(self):
        with pytest.raises(MessageError, match="Invalid source"):
            Message.new("request", {}, source="hacker")

    def test_unknown_workflow_is_lenient(self):
        """Without a matching workflow in the registry, only structural validation applies."""
        raw = {
            "id": "abc-123",
            "type": "custom_type",
            "workflow": "unknown_workflow",
            "version": 1,
            "timestamp": "2025-01-01T00:00:00",
            "trace_id": "trace-xyz",
            "payload": {"data": 1},
            "metadata": {"retry_count": 0, "source": "custom_agent"},
        }
        msg = Message(raw)
        assert msg.type == "custom_type"
        assert msg.workflow == "unknown_workflow"
        assert msg.source == "custom_agent"


class TestMessageSerialization:
    def test_roundtrip_bytes(self):
        original = Message.new("image_task", {"prompt": "test"})
        data = original.to_bytes()
        restored = Message.from_bytes(data)
        assert restored.id == original.id
        assert restored.type == original.type
        assert restored.workflow == original.workflow
        assert restored.payload == original.payload

    def test_from_bytes_invalid_json(self):
        with pytest.raises(MessageError, match="Invalid JSON"):
            Message.from_bytes(b"not json")

    def test_to_dict(self):
        msg = Message.new("request", {"key": "value"})
        d = msg.to_dict()
        assert d["type"] == "request"
        assert d["workflow"] == "coloring"
        assert d["payload"]["key"] == "value"

    def test_repr(self):
        msg = Message.new("request", {})
        r = repr(msg)
        assert msg.id[:8] in r
        assert "request" in r
        assert "coloring" in r


class TestMessageValidation:
    def test_missing_id_raises(self):
        with pytest.raises(MessageError, match="Missing or invalid 'id'"):
            Message({"type": "request", "version": 1, "timestamp": "x",
                     "trace_id": "x", "payload": {},
                     "metadata": {"retry_count": 0, "source": "user"}})

    def test_no_workflow_defaults_to_coloring(self):
        """Backward compat: messages without workflow field get 'coloring'."""
        msg = Message({
            "id": "x", "type": "request", "version": 1, "timestamp": "x",
            "trace_id": "x", "payload": {},
            "metadata": {"retry_count": 0, "source": "user"},
        })
        assert msg.workflow == "coloring"


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
        assert new_msg.workflow == msg.workflow  # workflow preserved
        assert new_msg.payload["refined"] == "data"
        assert new_msg.source == "orchestrator"
        assert new_msg.trace_id == msg.trace_id  # same trace

    def test_with_payload_new_workflow(self):
        msg = Message.new("research_request", {"raw": "data"}, workflow="research")
        new_msg = msg.with_payload({"refined": "data"}, new_type="research_task",
                                   new_workflow="research")
        assert new_msg.workflow == "research"
        assert new_msg.type == "research_task"
