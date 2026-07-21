# Contracts

Abstract base classes defining the interfaces for every pluggable component.
Implementations live in `src/` or `src/queue_backends/`.

## Interface Map

| Contract | Implemented By | Purpose |
|---|---|---|
| `queue.py` | `queue_backends/file_queue.py`, `memory_queue.py` | Message queue read/write/ack |
| `worker.py` | `workers/reasoning_worker.py`, `image_worker.py` | Worker lifecycle and processing |
| `orchestrator.py` | `orchestrator/pipeline.py` | Queue routing and state transitions |
| `serializer.py` | `core/message.py` | Encode/decode messages |
| `storage.py` | `storage/local_storage.py` | Save and retrieve artifacts |

## Contract Rules

- ABCs define methods only (no implementation)
- Every method has a docstring specifying preconditions and postconditions
- Implementations must pass the corresponding contract test suite
