#!/usr/bin/env bash
set -euo pipefail

# Start the village visualization and bridge

echo "Starting Village Bridge..."
python -m src.entrypoints.village_bridge --queue-dir .queues/coloring &
BRIDGE_PID=$!

echo "Starting Village UI..."
cd apps/village
npm run dev &
VILLAGE_PID=$!
cd ../..

echo "Village running:  Bridge=$BRIDGE_PID  UI=$VILLAGE_PID"
echo "Open http://localhost:3000"

trap 'echo "Shutting down..."; kill $BRIDGE_PID $VILLAGE_PID 2>/dev/null; wait' INT TERM
wait
