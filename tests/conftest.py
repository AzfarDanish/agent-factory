"""Shared test fixtures for the AI Factory."""
from __future__ import annotations

import pytest
import tempfile
import json
from pathlib import Path


@pytest.fixture(autouse=True)
def auto_reset_registry():
    """Reset the workflow registry singleton before each test, then reload.

    Ensures tests don't leak registry state between each other.
    """
    from src.registry import WorkflowRegistry, WORKFLOWS_DIR
    WorkflowRegistry.reset()
    reg = WorkflowRegistry.get_instance()
    reg.load_all()
    yield
    WorkflowRegistry.reset()


@pytest.fixture
def temp_file_queue():
    """Create a temporary directory with file-based queue files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        queue_dir = Path(tmpdir) / ".queues"
        queue_dir.mkdir(parents=True, exist_ok=True)

        queues = {
            "requests": queue_dir / "requests.jsonl",
            "reasoning": queue_dir / "reasoning.jsonl",
            "image": queue_dir / "image.jsonl",
            "completed": queue_dir / "completed.jsonl",
            "dlq": queue_dir / "dlq.jsonl",
        }

        for q in queues.values():
            q.parent.mkdir(parents=True, exist_ok=True)
            q.touch()

        yield queues


@pytest.fixture
def sample_request():
    """A valid coloring page request."""
    return {
        "prompt": "a friendly dragon in a meadow",
        "age_group": "child",
        "style": "cartoon",
        "theme": "fantasy",
        "quantity": 1,
    }


@pytest.fixture
def valid_envelope():
    """A complete message envelope ready for queue transport."""
    import uuid
    from datetime import datetime, timezone

    return {
        "id": str(uuid.uuid4()),
        "type": "request",
        "workflow": "coloring",
        "version": 1,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trace_id": str(uuid.uuid4()),
        "payload": {
            "prompt": "a friendly dragon in a meadow",
            "age_group": "child",
            "style": "cartoon",
        },
        "metadata": {
            "retry_count": 0,
            "source": "user",
        },
    }


@pytest.fixture
def mock_deepseek_response():
    """Simulated DeepSeek API response."""
    return {
        "refined_prompt": (
            "Black and white line art coloring page of a friendly cartoon "
            "dragon standing in a meadow with flowers. Thick clear outlines, "
            "white background, no shading, child-friendly simplicity."
        ),
        "negative_prompt": "colors, shading, gradients, complex backgrounds, text, letters, realistic details",
        "confidence": 0.95,
    }


@pytest.fixture
def mock_gpt_image_response():
    """Simulated GPT Image 1 API response metadata."""
    return {
        "model": "dall-e-3",
        "generation_time_ms": 4500,
    }
