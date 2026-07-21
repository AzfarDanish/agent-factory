# Storage — Artifact Persistence

Generated images are stored through the storage layer. The naming convention
is enforced here to ensure every artifact has a deterministic, traceable path.

## Modules

| Module | Responsibility |
|---|---|
| `local_storage.py` | Local filesystem read/write/delete |
| `naming.py` | File naming convention: `{request_id}_{trace_id}_{timestamp}.png` |

## Output Layout

```
output/
├── toddler/
│   ├── 2026-07-21/
│   │   ├── req_abc123_ts_14-30-00.png
│   │   └── req_def456_ts_14-31-15.png
├── child/
│   └── ...
├── teen/
├── adult/
└── metadata/
    └── {request_id}.json        ← Generation metadata
```
