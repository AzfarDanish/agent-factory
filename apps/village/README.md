# Village — Pipeline Visualization

A top-down 2D village that visualizes the coloring factory pipeline in real time.

## How It Works

```
Factory Backend                    Village App
┌─────────────────┐              ┌──────────────┐
│ Orchestrator    │              │  Next.js UI  │
│ → writes queues │              │              │
│                 │  WebSocket   │  Buildings = │
│ Village Bridge  │◄────────────►│  stages      │
│ → monitors      │              │              │
│   queues        │              │  Agents =    │
│ → broadcasts    │              │  active jobs │
│   events        │              │              │
└─────────────────┘              │  Day/night = │
                                 │  workload    │
                                 └──────────────┘
```

## Buildings Map

| Building | Pipeline Stage | Visual Cue |
|---|---|---|
| Gate | Request entry | Glows when requests arrive |
| Library (Church) | Reasoning (DeepSeek) | Door opens, candle lit |
| Artisan Workshop | Image gen (GPT) | Chimney smokes |
| Town Hall | Completed | Banners raise, celebration |
| The Pit | Failed | Red glow, warning |

## Day/Night Cycle

- **Day** — idle or light load
- **Dusk** — moderate load
- **Night** — heavy load (torches lit)
- **Dawn** — recovering

## Run

```bash
# Terminal 1: Start the bridge
python -m src.entrypoints.village_bridge

# Terminal 2: Start the village UI
cd apps/village
npm install
npm run dev
```

Open http://localhost:3000 to see the village.

## Demo Mode

Without the bridge, the village auto-runs demo agents.
Set `demoMode` to `true` on the `VillageMap` component (already set in page.tsx).
