# Configuration

All configuration follows a precedence chain: defaults.yaml is the base, overridden by
environment-specific files, overridden by environment variables, overridden by CLI flags.

## Files

| File | Purpose |
|---|---|
| `defaults.yaml` | Base values for every setting |
| `pipeline.yaml` | Queue names, topic hierarchy, routing rules |
| `workers.yaml` | Per-worker timeouts, retries, concurrency limits |
| `apis.yaml` | DeepSeek and GPT Image 1 endpoints, rate limits |
| `storage.yaml` | Output paths, naming patterns, retention policy |

## Environment Variables

All env vars follow the pattern `FACTORY_{SECTION}_{KEY}`.
Example: `FACTORY_DEEPSEEK_API_KEY`, `FACTORY_QUEUE_FILE_PATH`.

See `deploy/env/.env.example` for the full inventory.
