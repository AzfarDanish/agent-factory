# Workers — AI Model Adapters

Each worker wraps exactly one AI model. Workers never call each other — they
read from an input queue and write to an output queue.

## Workers

| Worker | Model | Input Queue | Output Queue |
|---|---|---|---|
| `reasoning_worker.py` | DeepSeek | `coloring.reasoning` | `coloring.image` |
| `image_worker.py` | GPT Image 1 | `coloring.image` | `coloring.completed` |
| `base.py` | — | — | — (base lifecycle class) |

## Adding a Worker

1. Create the worker file
2. Extend `base.py` (or implement `contracts/worker.py` directly)
3. Register in `config/workers.yaml`
4. Add a run script in `scripts/`
