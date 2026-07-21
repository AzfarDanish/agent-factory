# Coloring Page Factory

A queue-driven AI factory that produces coloring pages on demand.

**Architecture:**
- **Hermes** — orchestrator only (no reasoning, no image generation)
- **DeepSeek** — prompt reasoning and refinement
- **GPT Image 1** — image generation
- **Queues** — all worker communication (never direct)

## Quickstart

```bash
# Install
pip install -r requirements.txt

# Run the factory
./scripts/run.sh

# Submit a request
python -m src.entrypoints.cli submit --prompt "a dragon in a forest" --age-group child
```

## Project Map

| Directory | Responsibility |
|---|---|
| `schema/` | Message payload schemas (JSON Schema) |
| `config/` | Pipeline, worker, and API configuration |
| `contracts/` | Abstract interfaces (ABCs) |
| `src/core/` | Domain logic and validation |
| `src/queue_backends/` | Queue implementations |
| `src/workers/` | DeepSeek and GPT worker adapters |
| `src/orchestrator/` | State machine, pipeline routing, error handling |
| `src/entrypoints/` | CLI, Hermes bridge, API |
| `src/storage/` | Artifact output and naming |
| `src/config/` | Configuration loader |
| `tests/` | Unit, integration, and e2e tests |
| `scripts/` | Operational scripts |
| `deploy/` | Docker and environment configs |

## Principles

1. Queue-only communication. No direct worker calls.
2. Every message is idempotent.
3. Workers are stateless.
4. Fail isolated. Crashes never cascade.
5. Build incrementally. Phase 1 = file queues. Phase N = Redis + clusters.
