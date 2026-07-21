# Changelog

## Phase 0 — Foundation

- Project structure and architecture document
- Schema registry (message payload definitions)
- Configuration contracts (YAML defaults)
- Abstract interfaces (ABCs)
- Domain model: coloring page rules and constraints
- File queue backend
- CLI entry point

## Phase 1 — Core Pipeline

- Orchestrator state machine
- Queue routing pipeline
- Reasoning worker (DeepSeek)
- Image worker (GPT Image 1)
- Error handler with retry policy
- Storage backend

## Phase 2 — Hardening

- Integration tests
- Docker deployment
- Graceful shutdown
- Health checks
- Logging and trace propagation
