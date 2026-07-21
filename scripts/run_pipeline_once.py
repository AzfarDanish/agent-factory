"""Run the pipeline for any pending requests. Called after form submission."""

import sys
import os
from pathlib import Path
# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env from deploy/env/ (user's API keys)
from dotenv import load_dotenv
env_path = Path(__file__).resolve().parent.parent / "deploy" / "env" / ".env"
if env_path.exists():
    load_dotenv(env_path)
    print(f"[pipeline] Loaded env from {env_path}")

# Check API keys
deepseek_key = os.environ.get('FACTORY_DEEPSEEK_API_KEY', '')
openai_key = os.environ.get('FACTORY_OPENAI_API_KEY', '')
print(f"[pipeline] DeepSeek API key: {'set' if deepseek_key else 'NOT SET'}")
print(f"[pipeline] OpenAI API key:  {'set' if openai_key else 'NOT SET'}")
sys.stdout.flush()

from src.queue_backends.file_queue import FileQueue
from src.orchestrator.pipeline import Pipeline
from src.workers.reasoning_worker import ReasoningWorker
from src.workers.image_worker import ImageWorker
from src.core.message import Message


def run_pipeline(queue_dir='.queues/coloring', output_dir='output'):
    q = FileQueue(queue_dir)
    q.connect()
    p = Pipeline(queue_dir=queue_dir)
    p._ensure_queues()

    # Check for API keys from environment
    deepseek_key = os.environ.get('FACTORY_DEEPSEEK_API_KEY', '')
    openai_key = os.environ.get('FACTORY_OPENAI_API_KEY', '')

    rw = ReasoningWorker(
        queue_dir=queue_dir,
        use_api=bool(deepseek_key),
        api_key=deepseek_key or '',
    )
    iw = ImageWorker(
        queue_dir=queue_dir,
        output_dir=output_dir,
        use_api=bool(openai_key),
        api_key=openai_key or '',
    )

    count = 0
    max_requests = 3

    for _ in range(max_requests):
        raw = q.consume('requests', timeout=0.5)
        if raw is None:
            break

        msg = Message.from_bytes(raw)
        target = p._validate_and_route(msg)
        q.publish('reasoning', target.to_bytes())

        raw = q.consume('reasoning', timeout=5.0)
        result = rw.process(Message.from_bytes(raw))
        q.publish('image', result.to_bytes())

        raw = q.consume('image', timeout=5.0)
        img_result = iw.process(Message.from_bytes(raw))
        q.publish('completed', img_result.to_bytes())

        count += 1
        model = 'deepseek+openai' if (deepseek_key and openai_key) else 'placeholder'
        print(f'[{model}] {msg.trace_id[:8]} -> {img_result.payload["image_path"]}')

    print(f'Done. {count} requests processed.')
    return count


if __name__ == '__main__':
    run_pipeline()
