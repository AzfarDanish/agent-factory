# Deploy — Infrastructure

## Contents

| File | Purpose |
|---|---|
| `Dockerfile` | Multi-stage build for worker images |
| `docker-compose.yml` | Phase 1: file queues + all workers |
| `.dockerignore` | Excluded files for Docker builds |
| `env/.env.example` | Every environment variable documented |

## Usage

```bash
# Build and run
docker compose up

# Run in background
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

## Environment Variables

Copy `env/.env.example` to `.env` and fill in API keys.
