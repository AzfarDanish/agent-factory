"""Tests for file and memory queue backends."""

import tempfile
from pathlib import Path
import pytest
from src.queue_backends.file_queue import FileQueue
from src.queue_backends.memory_queue import MemoryQueue


@pytest.fixture
def file_queue():
    with tempfile.TemporaryDirectory() as tmpdir:
        q = FileQueue(Path(tmpdir) / "queues")
        q.connect()
        yield q


@pytest.fixture
def mem_queue():
    return MemoryQueue()


class TestFileQueue:
    def test_publish_and_consume(self, file_queue):
        file_queue.publish("test", b"hello")
        msg = file_queue.consume("test", timeout=2.0)
        assert msg == b"hello"

    def test_consume_empty_returns_none(self, file_queue):
        msg = file_queue.consume("empty", timeout=0.5)
        assert msg is None

    def test_queue_length(self, file_queue):
        file_queue.publish("test", b"msg1")
        file_queue.publish("test", b"msg2")
        assert file_queue.queue_length("test") == 2
        file_queue.consume("test", timeout=1.0)
        assert file_queue.queue_length("test") == 1

    def test_requeue(self, file_queue):
        file_queue.publish("test", b"original")
        file_queue.requeue("test", b"requeued")
        assert file_queue.queue_length("test") == 2

    def test_multiple_queues_independent(self, file_queue):
        file_queue.publish("q1", b"a")
        file_queue.publish("q2", b"b")
        assert file_queue.queue_length("q1") == 1
        assert file_queue.queue_length("q2") == 1

    def test_reset_cursor_rereads_messages(self, file_queue):
        file_queue.publish("test", b"msg1")
        file_queue.consume("test", timeout=1.0)
        assert file_queue.queue_length("test") == 0
        file_queue.reset_cursor("test")
        assert file_queue.queue_length("test") == 1


class TestMemoryQueue:
    def test_publish_and_consume(self, mem_queue):
        mem_queue.publish("test", b"hello")
        msg = mem_queue.consume("test", timeout=1.0)
        assert msg == b"hello"

    def test_consume_empty_returns_none(self, mem_queue):
        msg = mem_queue.consume("empty", timeout=0.5)
        assert msg is None

    def test_queue_length(self, mem_queue):
        mem_queue.publish("test", b"a")
        mem_queue.publish("test", b"b")
        assert mem_queue.queue_length("test") == 2
        mem_queue.consume("test", timeout=1.0)
        assert mem_queue.queue_length("test") == 1

    def test_fifo_order(self, mem_queue):
        mem_queue.publish("test", b"first")
        mem_queue.publish("test", b"second")
        assert mem_queue.consume("test", timeout=1.0) == b"first"
        assert mem_queue.consume("test", timeout=1.0) == b"second"

    def test_requeue(self, mem_queue):
        mem_queue.publish("test", b"original")
        mem_queue.requeue("test", b"requeued")
        assert mem_queue.queue_length("test") == 2
