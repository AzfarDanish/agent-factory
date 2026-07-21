# Stage 1: Base
FROM python:3.11-slim AS base

WORKDIR /factory
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Orchestrator
FROM base AS orchestrator
COPY . .
CMD ["python", "-m", "src.orchestrator.pipeline"]

# Stage 3: Reasoning Worker
FROM base AS reasoning-worker
COPY . .
CMD ["python", "-m", "src.workers.reasoning_worker"]

# Stage 4: Image Worker
FROM base AS image-worker
COPY . .
CMD ["python", "-m", "src.workers.image_worker"]
