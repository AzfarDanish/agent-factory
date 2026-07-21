# Core — Domain Logic

Pure domain logic with zero I/O. Everything in this module can be unit tested
without mocks, queues, APIs, or filesystem access.

## Modules

| Module | Responsibility |
|---|---|
| `message.py` | Envelope creation, validation, serialization |
| `coloring_domain.py` | Coloring page rules: complexity calculation, age group constraints, style validation |
| `prompt_rules.py` | Prompt engineering: templates, style presets, negative prompt generation |

## Design Rules

- No imports from `queue_backends`, `workers`, `orchestrator`, or any I/O module
- No network calls
- No filesystem access
- Pure functions preferred
