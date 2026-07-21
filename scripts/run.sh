#!/usr/bin/env bash
set -euo pipefail

# Coloring Page Factory — Launch All Components

echo "Starting Coloring Page Factory..."

# Ensure queue directories exist
mkdir -p .queues/coloring

# Start orchestrator
echo "Starting orchestrator..."
python -m src.orchestrator.pipeline &
ORCHESTRATOR_PID=$!

# Start reasoning worker
echo "Starting reasoning worker (DeepSeek)..."
python -m src.workers.reasoning_worker &
REASONING_PID=$!

# Start image worker
echo "Starting image worker (GPT Image 1)..."
python -m src.workers.image_worker &
IMAGE_PID=$!

echo "Factory running. PIDs: orchestrator=$ORCHESTRATOR_PID reasoning=$REASONING_PID image=$IMAGE_PID"
echo "Press Ctrl+C to stop."

# Trap SIGINT/SIGTERM for graceful shutdown
trap 'echo "Shutting down..."; kill $ORCHESTRATOR_PID $REASONING_PID $IMAGE_PID 2>/dev/null; wait; echo "Stopped."' INT TERM

# Wait for any child to exit
wait
