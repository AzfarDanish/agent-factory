"""CLI entrypoint — submit coloring requests from the command line.

Usage:
    python -m src.entrypoints.cli submit "a friendly dragon" --age-group child --style cartoon
    python -m src.entrypoints.cli submit "a mandala pattern" --age-group adult --style mandala -n 3
"""

import argparse
import sys
import json
from pathlib import Path

from src.core.message import Message
from src.core.coloring_domain import validate_request
from src.queue_backends.file_queue import FileQueue


def submit(args: argparse.Namespace) -> None:
    """Validate a request and publish it to the requests queue."""
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

    # Create message
    msg = Message.new(
        "request",
        payload=validated,
        source="user",
    )

    # Publish to queue
    queue_dir = Path(args.queue_dir)
    queue = FileQueue(queue_dir)
    queue.connect()
    queue.publish("requests", msg.to_bytes())

    print(f"Submitted: {msg.id[:8]}...")
    print(f"  Prompt: {validated['prompt']}")
    print(f"  Style:  {validated['style']}")
    print(f"  Age:    {validated['age_group']}")
    print(f"  Qty:    {validated['quantity']}")
    print(f"  Queue:  {queue_dir}/requests.jsonl")


def list_queue(args: argparse.Namespace) -> None:
    """List messages in a queue."""
    queue = FileQueue(Path(args.queue_dir))
    queue.connect()
    length = queue.queue_length(args.queue_name)
    print(f"Queue '{args.queue_name}': {length} messages pending")


def main() -> None:
    parser = argparse.ArgumentParser(description="Coloring Page Factory CLI")
    parser.add_argument("--queue-dir", default=".queues/coloring",
                        help="Queue directory path")

    sub = parser.add_subparsers(dest="command", required=True)

    # submit command
    submit_p = sub.add_parser("submit", help="Submit a coloring request")
    submit_p.add_argument("prompt", help="Description of the coloring page")
    submit_p.add_argument("--age-group", "-a", default="child",
                          choices=["toddler", "child", "teen", "adult"])
    submit_p.add_argument("--style", "-s", default="simple",
                          choices=["simple", "detailed", "mandala", "cartoon", "realistic"])
    submit_p.add_argument("--quantity", "-n", type=int, default=1)

    # list command
    list_p = sub.add_parser("list", help="List messages in a queue")
    list_p.add_argument("queue_name", help="Queue name (e.g. requests, reasoning, image)")

    args = parser.parse_args()

    if args.command == "submit":
        submit(args)
    elif args.command == "list":
        list_queue(args)


if __name__ == "__main__":
    main()
