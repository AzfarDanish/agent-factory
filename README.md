# Coloring Page Factory

A queue-driven AI factory that produces coloring pages on demand.

**Architecture:**
- **Hermes** — orchestrator only (no reasoning, no image generation)
- **DeepSeek** — prompt reasoning and refinement
- **GPT Image 1 / DALL-E 3** — image generation
- **Queues** — all worker communication (never direct)

---

## Quick Start

### 1. Set API keys

```bash
nano ~/Projects/coloring-factory/deploy/env/.env
```

Contents:
```
FACTORY_DEEPSEEK_API_KEY=sk-your-deepseek-key
FACTORY_OPENAI_API_KEY=sk-your-openai-key
```

Without keys the pipeline works but generates placeholder shapes.

### 2. Start everything (one command)

```bash
cd ~/Projects/coloring-factory/apps/village && pnpm run dev:all
```

This starts the bridge server (port 3001) and the village UI (port 3000) together.

Open `http://localhost:3000`.

### 3. Submit a request

Type a prompt into the village form, pick age/style, click Generate.

### 4. (Optional) Run from terminal

```bash
cd ~/Projects/coloring-factory
python -m src.entrypoints.cli submit "a dragon" --age-group child --style cartoon
python scripts/run_pipeline_once.py
```

---

## How it works

```
You submit a request
  → Village form writes to queue file
  → Bridge detects new message, broadcasts event
  → Village agents animate: Gatehouse → Church → Artisan Hall → Archive
  → Pipeline: validate → DeepSeek refines prompt → DALL-E generates image
  → Image saved to: output/{style}/{date}/{request_id}.png
```

---

## Commands

| What | Command |
|---|---|
| Start everything | `cd apps/village && pnpm run dev:all` |
| Start bridge only | `python -m src.entrypoints.village_bridge` |
| Start village only | `cd apps/village && pnpm run dev` |
| Submit request | `python -m src.entrypoints.cli submit "prompt" --age-group child --style cartoon` |
| Run pipeline | `python scripts/run_pipeline_once.py` |
| Run tests | `python -m pytest src/ tests/ -v` |
| Stop all | Ctrl+C |

---

## Project structure

| Directory | Purpose |
|---|---|
| `src/core/` | Message envelope, coloring rules, prompt templates |
| `src/queue_backends/` | File-based queue (JSONL) |
| `src/workers/` | DeepSeek reasoner + DALL-E generator |
| `src/orchestrator/` | Pipeline routing, state machine, error handling |
| `src/entrypoints/` | CLI + Village Bridge SSE event server |
| `apps/village/` | Next.js village visualization |
| `config/` | YAML config for pipeline, workers, APIs |
| `contracts/` | Abstract interfaces (ABCs) |
| `schema/` | JSON message schemas |
| `tests/` | 45 unit + integration tests |
