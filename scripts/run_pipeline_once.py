"""Run the pipeline for any pending requests. Called after form submission."""

import sys
import os
# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

    rw = ReasoningWorker(queue_dir=queue_dir, use_api=False)
    iw = ImageWorker(queue_dir=queue_dir, output_dir=output_dir, use_api=False)

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
        print(f'Processed: {msg.trace_id[:8]} → {img_result.payload["image_path"]}')

    print(f'Done. {count} requests processed.')
    return count


if __name__ == '__main__':
    run_pipeline()
