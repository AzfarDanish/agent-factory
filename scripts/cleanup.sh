#!/usr/bin/env bash
set -euo pipefail

# Coloring Page Factory — Cleanup

echo "Cleaning up Coloring Page Factory state..."

# Remove queues
rm -rf .queues

# Remove output images
rm -rf output

# Remove Python cache
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -type f -name '*.pyc' -delete 2>/dev/null || true

# Remove temp test artifacts
rm -rf .pytest_cache

echo "Cleanup complete."
