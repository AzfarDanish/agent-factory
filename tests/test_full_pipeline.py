"""Full pipeline integration tests — exercises each module in sequence.

Uses file queues with template fallbacks (no API keys needed).
"""

import tempfile
from pathlib import Path

from src.core.message import Message
from src.queue_backends.file_queue import FileQueue
from src.orchestrator.pipeline import Pipeline
from src.workers.reasoning_worker import ReasoningWorker
from src.workers.image_worker import ImageWorker


def test_full_pipeline_end_to_end():
    """Submit a request → pipeline validates → reasoning worker → image worker → completed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        queue_dir = Path(tmpdir) / "queues"
        output_dir = Path(tmpdir) / "output"

        # Setup queue
        queue = FileQueue(str(queue_dir))
        queue.connect()

        # Setup pipeline with queues
        pipeline = Pipeline(queue_dir=str(queue_dir))
        pipeline._ensure_queues()

        # Step 1: Submit a request
        msg = Message.new("request", {
            "prompt": "a dragon in a forest",
            "age_group": "child",
            "style": "cartoon",
            "quantity": 1,
        })
        queue.publish("requests", msg.to_bytes())

        # Step 2: Pipeline routes request → reasoning queue
        pipeline._process_queue("requests", None, None, pipeline._validate_and_route)

        # Verify it reached reasoning queue
        raw = queue.consume("reasoning", timeout=2.0)
        assert raw is not None, "Message did not reach reasoning queue"
        reasoning_msg = Message.from_bytes(raw)
        assert reasoning_msg.type == "reasoning_task"
        assert reasoning_msg.payload["raw_prompt"] == "a dragon in a forest"

        # Re-publish for the worker to consume
        queue.publish("reasoning", reasoning_msg.to_bytes())

        # Step 3: Reasoning worker processes it
        reasoning = ReasoningWorker(queue_dir=str(queue_dir), use_api=False)
        reasoning._queue.connect()
        raw = queue.consume("reasoning", timeout=2.0)
        assert raw is not None
        r_msg = Message.from_bytes(raw)
        result = reasoning.process(r_msg)
        assert result is not None
        assert result.type == "image_task"
        assert "refined_prompt" in result.payload
        assert "negative_prompt" in result.payload
        assert len(result.payload["refined_prompt"]) > 50, "Refined prompt too short"

        # Publish to image queue
        queue.publish("image", result.to_bytes())

        # Step 4: Image worker processes it
        image = ImageWorker(
            queue_dir=str(queue_dir),
            output_dir=str(output_dir),
            use_api=False,
        )
        raw = queue.consume("image", timeout=2.0)
        assert raw is not None
        i_msg = Message.from_bytes(raw)
        img_result = image.process(i_msg)
        assert img_result is not None
        assert img_result.type == "result"
        assert "image_path" in img_result.payload
        assert "metadata" in img_result.payload

        # Verify the image file exists
        image_path = Path(img_result.payload["image_path"])
        assert image_path.exists(), f"Image not found: {image_path}"
        assert image_path.stat().st_size > 100, "Image too small"

        # Verify metadata
        meta = img_result.payload["metadata"]
        assert meta["model"] == "placeholder"
        assert meta["generation_time_ms"] == 0

        print(f"PASS: {msg.trace_id[:8]} → {reasoning_msg.trace_id[:8]} → {result.trace_id[:8]} → {img_result.trace_id[:8]}")
        print(f"PASS: Image saved to {image_path}")


def test_pipeline_rejects_bad_requests():
    """Invalid requests go to DLQ, not to reasoning queue."""
    with tempfile.TemporaryDirectory() as tmpdir:
        queue_dir = Path(tmpdir) / "queues"
        queue = FileQueue(str(queue_dir))
        queue.connect()
        pipeline = Pipeline(queue_dir=str(queue_dir))
        pipeline._ensure_queues()

        # Submit invalid request (too short)
        msg = Message.new("request", {
            "prompt": "ab",
            "age_group": "child",
            "style": "simple",
        })
        queue.publish("requests", msg.to_bytes())

        pipeline._process_queue("requests", None, None, pipeline._validate_and_route)

        assert queue.queue_length("dlq") >= 1, "Bad request should go to DLQ"
        assert queue.queue_length("reasoning") == 0, "Bad request should NOT reach reasoning"


def test_reasoning_worker_template_fallback():
    """Reasoning worker produces valid output without API key."""
    with tempfile.TemporaryDirectory() as tmpdir:
        worker = ReasoningWorker(queue_dir=str(Path(tmpdir) / "queues"), use_api=False)

        msg = Message.new("reasoning_task", {
            "raw_prompt": "a friendly unicorn in a magical forest",
            "age_group": "child",
            "style": "cartoon",
        }, source="orchestrator")

        result = worker.process(msg)

        assert result is not None
        assert result.type == "image_task"
        assert len(result.payload["refined_prompt"]) > 50
        assert len(result.payload["negative_prompt"]) > 10
        assert result.payload["style"] == "cartoon"


def test_image_worker_placeholder():
    """Image worker produces a valid placeholder image without API key."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "output"
        worker = ImageWorker(
            queue_dir=str(Path(tmpdir) / "queues"),
            output_dir=str(output_dir),
            use_api=False,
        )

        msg = Message.new("image_task", {
            "refined_prompt": "Black and white line art of a dragon. White background. No colors.",
            "negative_prompt": "colors, shading",
            "style": "cartoon",
        }, source="orchestrator")

        result = worker.process(msg)

        assert result is not None
        assert result.type == "result"
        image_path = Path(result.payload["image_path"])
        assert image_path.exists()
        assert image_path.stat().st_size > 100
