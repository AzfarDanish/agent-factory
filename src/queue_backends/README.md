# Queue Backends — Message Transport

Pluggable queue implementations. All backends implement `contracts/queue.py`.

## Available Backends

| Backend | File | Phase | When to Use |
|---|---|---|---|
| File | `file_queue.py` | 1 | Development, single-machine, zero-dependency |
| Memory | `memory_queue.py` | 1 | Unit tests, single-process mode |
| Redis | `redis_queue.py` | 2 | Production, multi-worker, persistence needed |

## Adding a Backend

1. Create a new file in this directory
2. Implement every method from `contracts/queue.py`
3. Update `config/pipeline.yaml` to expose the new backend name
