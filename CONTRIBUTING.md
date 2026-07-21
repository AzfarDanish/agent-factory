# Contributing

## Adding a New Worker

1. Define the input/output payload schemas in `schema/`
2. Implement the worker ABC in `contracts/worker.py`
3. Create the worker in `src/workers/`
4. Register it in `config/pipeline.yaml`
5. Add a run script in `scripts/`
6. Write tests

## Adding a New Queue Backend

1. Implement `contracts/queue.py`
2. Place the implementation in `src/queue_backends/`
3. Update `config/pipeline.yaml` to select the backend
4. Write tests

## Adding a New Factory

A "factory" is a product line (e.g. Coloring Page Factory, Storybook Factory).
1. Create new schema files in `schema/` prefixed with the factory name
2. Add queue definitions to `config/pipeline.yaml`
3. Create factory-specific workers in `src/workers/`
4. Extend the orchestrator state machine

## Code Standards

- Tests co-located with source modules (unit) and in `tests/` (integration)
- Every module has a README
- Every public method has a docstring
- No direct worker-to-worker communication
