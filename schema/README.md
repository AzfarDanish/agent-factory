# Schema Registry

Message payload schemas for the Coloring Page Factory. Every message on every queue
has a defined shape validated against these JSON Schema files before processing.

## Schema Index

| File | Queue | Description |
|---|---|---|
| `envelope.json` | (all queues) | Outer message wrapper |
| `request.json` | `coloring.requests` | User-submitted coloring request |
| `reasoning_task.json` | `coloring.reasoning` | Prompt refinement task for DeepSeek |
| `image_task.json` | `coloring.image` | Image generation task for GPT Image 1 |
| `result.json` | `coloring.completed` | Completed coloring page result |
| `error.json` | `coloring.dlq` | Dead letter queue entry |
| `coloring_page.json` | (domain model) | Definition of what a coloring page is |

## Adding a New Message Type

1. Create a JSON Schema file in this directory
2. Reference it in the queue's config in `config/pipeline.yaml`
3. Register the schema in the message validator
