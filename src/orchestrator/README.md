# Orchestrator — Pipeline Management

The orchestrator is the brain of the factory. It manages state transitions,
routes messages between queues, and handles errors. Hermes Agent runs
the orchestrator.

## Modules

| Module | Responsibility |
|---|---|
| `state_machine.py` | Workflow state definitions and transition rules |
| `pipeline.py` | Queue routing: read from A, validate, write to B |
| `error_handler.py` | Error classification (transient/fatal), retry policy, DLQ routing |

## Flow

```
Orchestrator reads coloring.requests
  → validates against schema/request.json
  → writes to coloring.reasoning (via state_machine)

Reasoning Worker reads coloring.reasoning
  → calls DeepSeek
  → writes to coloring.image

Image Worker reads coloring.image
  → calls GPT Image 1
  → writes to coloring.completed

Orchestrator reads coloring.completed
  → stores image via storage/
  → marks workflow complete
```
