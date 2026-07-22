"""CLI entrypoint — submit jobs to the AI Factory from the command line.

Usage:
    python -m src.entrypoints.cli submit "a friendly dragon" --workflow coloring --age-group child --style cartoon
    python -m src.entrypoints.cli submit "effects of AI on healthcare" --workflow research
    python -m src.entrypoints.cli list requests --workflow coloring
"""
from __future__ import annotations

import argparse
import sys
import json
from pathlib import Path

from src.core.message import Message
from src.queue_backends.file_queue import FileQueue


def submit(args: argparse.Namespace) -> None:
    """Validate a request and publish it to the entry queue for the workflow."""
    workflow = args.workflow

    if workflow == "coloring":
        # Coloring workflow has specific validation
        from src.core.coloring_domain import validate_request
        try:
            validated = validate_request(
                prompt=args.prompt,
                age_group=args.age_group,
                style=args.style,
                quantity=args.quantity,
            )
        except ValueError as e:
            print(f"Validation error: {e}", file=sys.stderr)
            sys.exit(1)

        payload = validated
    elif workflow == "research":
        payload = {
            "query": args.prompt,
            "depth": "standard",
            "max_sources": 5,
        }
    elif workflow == "documentation":
        payload = {
            "topic": args.prompt,
            "document_type": "guide",
            "format": "markdown",
            "tone": "formal",
            "max_sections": 6,
        }
    else:
        # Generic fallback: pass prompt as-is
        payload = {"prompt": args.prompt}

    # Create message
    msg = Message.new(
        "request",
        payload=payload,
        source="user",
        workflow=workflow,
    )

    # Publish to the entry queue for this workflow
    # Currently all workflows use "requests" as the entry queue
    # In the future, workflos could have workflow-specific queues
    queue_dir = Path(args.queue_dir)
    queue = FileQueue(queue_dir)
    queue.connect()
    queue.publish("requests", msg.to_bytes())

    print(f"Submitted [{workflow}]: {msg.id[:8]}...")
    print(f"  Workflow: {workflow}")
    print(f"  Payload:  {json.dumps(payload, indent=2)}")
    print(f"  Queue:    {queue_dir}/requests.jsonl")


def list_queue(args: argparse.Namespace) -> None:
    """List messages in a queue."""
    queue = FileQueue(Path(args.queue_dir))
    queue.connect()
    length = queue.queue_length(args.queue_name)
    print(f"Queue '{args.queue_name}': {length} messages pending")


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Factory CLI")
    parser.add_argument("--queue-dir", default=".queues/coloring",
                        help="Queue directory path")
    parser.add_argument("--workflow", "-w", default="coloring",
                        choices=["coloring", "research", "documentation"],
                        help="Workflow pipeline to use")

    sub = parser.add_argument_group("commands")
    subs = parser.add_subparsers(dest="command", required=True)

    # submit command
    submit_p = subs.add_parser("submit", help="Submit a job to the pipeline")
    submit_p.add_argument("prompt", help="Job description")
    submit_p.add_argument("--age-group", "-a", default="child",
                          choices=["toddler", "child", "teen", "adult"],
                          help="Coloring: target age group")
    submit_p.add_argument("--style", "-s", default="simple",
                          choices=["simple", "detailed", "mandala", "cartoon", "realistic"],
                          help="Coloring: art style")
    submit_p.add_argument("--quantity", "-n", type=int, default=1,
                          help="Coloring: number of variations")

    # list command
    list_p = subs.add_parser("list", help="List messages in a queue")
    list_p.add_argument("queue_name", help="Queue name (e.g. requests, reasoning, image)")

    args = parser.parse_args()

    if args.command == "submit":
        submit(args)
    elif args.command == "list":
        list_queue(args)


if __name__ == "__main__":
    main()
