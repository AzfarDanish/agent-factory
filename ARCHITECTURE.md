# Coloring Page Factory — Architecture

## System Statement

A production-grade AI factory that produces coloring pages on demand. Hermes orchestrates the pipeline exclusively. No reasoning or image generation flows through Hermes. Workers are isolated, queue-connected, and never communicate directly.

## First Principles

| Principle | Rule |
|---|---|
| **Single Responsibility** | Hermes orchestrates. DeepSeek reasons. GPT Image 1 generates. No overlap. |
| **Queue-Only Communication** | Workers publish and subscribe to queues. Zero direct calls between workers. |
| **Idempotent Messages** | Every message carries a unique ID. Processing the same message twice produces the same result. |
| **Fail Isolated** | A worker crash never cascades. DLQ captures failures. Orchestrator decides retry or abort. |
| **Incremental Build** | Phase 1 = file queues + single worker pair. Phase N = Redis + clusters + monitoring. |

## Component Architecture

```
┌────────────────────────────────────────────────────────────┐
│                       Hermes Agent                         │
│                   (Orchestrator — no reasoning,            │
│                    no image generation)                    │
│                                                            │
│  ┌──────────────────┐   ┌──────────────┐   ┌───────────┐  │
│  │ Workflow State   │   │ Queue Router │   │ Result    │  │
│  │ Machine          │──▶│ (read/write  │──▶│ Collector │  │
│  │                  │   │  queues)     │   │           │  │
│  └──────────────────┘   └──────┬───────┘   └───────────┘  │
│                                │                           │
└────────────────────────────────┼───────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │         Queues           │
                    │                         │
                    │  coloring.requests      │
                    │  coloring.reasoning     │
                    │  coloring.image         │
                    │  coloring.completed     │
                    │  coloring.dlq           │
                    └───┬─────────────────┬───┘
                        │                 │
              ┌─────────▼──────┐   ┌──────▼──────────┐
              │ Reasoning      │   │ Image            │
              │ Worker         │   │ Worker           │
              │ (DeepSeek)     │   │ (GPT Image 1)    │
              │                │   │                  │
              │ Reads reqs     │   │ Reads prompts    │
              │ Writes prompts │   │ Writes images    │
              └────────────────┘   └─────────────────┘
```

## Queue Topology

| Queue | Producer | Consumer | Payload |
|---|---|---|---|
| `coloring.requests` | User / API | Orchestrator | Raw user request string |
| `coloring.reasoning` | Orchestrator | Reasoning Worker | {request_id, raw_prompt, params} |
| `coloring.image` | Reasoning Worker | Image Worker | {request_id, refined_prompt, style, negative} |
| `coloring.completed` | Image Worker | Orchestrator | {request_id, image_ref, metadata} |
| `coloring.dlq` | Any worker | (manual) | {request_id, error, trace, original_msg} |

## Message Envelope

Every queue message follows a standard envelope:

```json
{
  "id": "uuid-v4",
  "type": "request | reasoning_task | image_task | result | error",
  "version": 1,
  "timestamp": "ISO-8601",
  "trace_id": "uuid-v4",
  "payload": { },
  "metadata": {
    "retry_count": 0,
    "source": "user | orchestrator | reasoning_worker | image_worker"
  }
}
```

## Workflow State Machine

```
[REQUEST] ──► [REASONING] ──► [GENERATING] ──► [COMPLETED]
                │                  │
                ▼                  ▼
             [FAILED]          [FAILED]
```

Transitions are driven by queue events. Orchestrator never blocks — it polls queues and reacts.

## Worker Contract

Every worker MUST:
- Read from exactly one input queue
- Write to exactly one output queue (or DLQ on failure)
- Be stateless (all state lives in the message)
- Log trace_id on every operation
- Process one message at a time (consumer pacing)

## Backend Strategy

| Phase | Queue Backend | Rationale |
|---|---|---|
| 1 (now) | File-based queues | Zero dependencies. Quick iteration. |
| 2 | Redis Streams | Persistent, fast, consumer groups. |
| 3 | RabbitMQ / NATS | High throughput, routing, observability. |

The queue abstraction layer (src/queue_backends/) makes swapping backends a config change.

## Project Structure

```
coloring-factory/
├── ARCHITECTURE.md        ← this file
├── README.md              ← setup guide
├── requirements.txt       ← Python deps
├── .env.example           ← all env vars documented
├── src/
│   ├── core/
│   │   ├── message.py     ← Message envelope, serialization
│   │   ├── queue.py       ← Queue ABC (interface)
│   │   └── worker.py      ← Base worker with lifecycle
│   ├── queue_backends/
│   │   ├── file_queue.py  ← Phase 1: JSON-line files
│   │   ├── memory_queue.py← For testing
│   │   └── redis_queue.py ← Phase 2+
│   ├── workers/
│   │   ├── reasoning.py   ← DeepSeek worker
│   │   └── image.py       ← GPT Image 1 worker
│   ├── orchestrator/
│   │   ├── workflow.py    ← State machine
│   │   └── pipeline.py    ← Queue routing logic
│   └── config/
│       └── settings.py    ← Env-driven config
├── tests/
│   ├── test_message.py
│   ├── test_queue.py
│   ├── test_workflow.py
│   └── test_pipeline.py
└── scripts/
    ├── run.sh             ← Launch orchestrator + workers
    └── demo.py            ← Submit a test coloring request
```

## Implementation Order

1. Core: Message envelope, Queue ABC, Worker base class
2. File queue backend (dev)
3. Config module
4. Orchestrator: Workflow state machine + pipeline router
5. Reasoning worker wrapper (DeepSeek API)
6. Image worker wrapper (GPT Image 1 API)
7. Integration: full pipeline end-to-end
8. Tests at every layer

## Non-Goals (Phase 1)

- No web UI
- No authentication/authorization
- No horizontal scaling
- No monitoring/alerting
- No persistent storage of generated images (beyond local files)
