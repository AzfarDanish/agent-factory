# Entrypoints — How Work Enters the Factory

Every way the system receives a coloring request. The orchestrator polls
the request queue — it doesn't care where requests come from.

## Entrypoints

| Entrypoint | File | Purpose |
|---|---|---|
| CLI | `cli.py` | Command-line submission: `coloring-factory submit "a dragon"` |
| Hermes Bridge | `hermes_bridge.py` | Hermes Agent tool binding: writes to coloring.requests |

## Adding an Entrypoint

1. Create the entrypoint file
2. Validate input against `schema/request.json`
3. Wrap in a message envelope and publish to `coloring.requests`
