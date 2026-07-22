"""Workflow registry — loads and validates workflow definitions.

Each workflow is a YAML file in config/workflows/ that defines:
- Stages and valid transitions
- Which queues serve each stage
- Allowed message types and sources
- Worker mappings

The registry is the single source of truth for what a workflow allows.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


logger = logging.getLogger(__name__)


# ── Default workflow (backward compat when no workflow is specified) ──────────
_DEFAULT_WORKFLOW = "coloring"

# ── Project root convention (mirrors config/loader.py) ────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
WORKFLOWS_DIR = PROJECT_ROOT / "config" / "workflows"


class WorkflowError(Exception):
    """Raised on workflow definition errors."""


@dataclass(frozen=True)
class WorkflowDefinition:
    """Immutable definition of a single workflow pipeline."""

    name: str
    description: str
    stages: list[str]
    transitions: dict[str, list[str]]
    stage_queues: dict[str, str]
    stage_message_types: dict[str, str]
    valid_message_types: set[str]
    valid_sources: set[str]
    max_retries: int = 3
    worker_map: dict[str, str] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowDefinition":
        """Parse and validate a raw YAML dict into a WorkflowDefinition."""
        name = data.get("name", "")
        if not name:
            raise WorkflowError("Workflow definition missing 'name'")

        stages = data.get("stages", [])
        if not stages:
            raise WorkflowError(f"Workflow '{name}': no stages defined")

        transitions = data.get("transitions", {})
        # Validate all transition targets are real stages
        all_stages_set = set(stages)
        for src, targets in transitions.items():
            if src not in all_stages_set:
                raise WorkflowError(
                    f"Workflow '{name}': transition source '{src}' not in stages {stages}"
                )
            for t in targets:
                if t not in all_stages_set:
                    raise WorkflowError(
                        f"Workflow '{name}': transition '{src}→{t}' target '{t}' "
                        f"not in stages {stages}"
                    )

        stage_queues = data.get("stage_queues", {})
        for s in stages:
            if s not in stage_queues and s not in ("failed",):
                raise WorkflowError(
                    f"Workflow '{name}': stage '{s}' has no queue in stage_queues"
                )

        stage_message_types = data.get("stage_message_types", {})
        for s in stages:
            if s not in stage_message_types and s not in ("failed",):
                raise WorkflowError(
                    f"Workflow '{name}': stage '{s}' has no message type"
                )

        valid_types = set(data.get("valid_message_types", []))
        valid_sources = set(data.get("valid_sources", []))

        return cls(
            name=name,
            description=data.get("description", ""),
            stages=stages,
            transitions=transitions,
            stage_queues=stage_queues,
            stage_message_types=stage_message_types,
            valid_message_types=valid_types or {"error"},
            valid_sources=valid_sources or {"orchestrator"},
            max_retries=data.get("max_retries", 3),
            worker_map=data.get("workers", {}),
            raw=data,
        )

    def can_transition(self, current: str, target: str) -> bool:
        """Check if a transition from current stage to target is valid."""
        allowed = self.transitions.get(current, [])
        return target in allowed

    def get_queue_for_stage(self, stage: str) -> str:
        """Return the queue name for a pipeline stage."""
        return self.stage_queues.get(stage, "dlq")

    def get_message_type_for_stage(self, stage: str) -> str:
        """Return the message type for a pipeline stage."""
        return self.stage_message_types.get(stage, "error")

    def is_valid_type(self, msg_type: str) -> bool:
        return msg_type in self.valid_message_types

    def is_valid_source(self, source: str) -> bool:
        return source in self.valid_sources

    def is_terminal(self, stage: str) -> bool:
        return len(self.transitions.get(stage, [])) == 0

    def get_worker_class_path(self, input_queue: str) -> str | None:
        """Return the fully-qualified class path for a worker consuming this queue."""
        return self.worker_map.get(input_queue)


# ── Registry singleton ────────────────────────────────────────────────────────


class WorkflowRegistry:
    """Singleton registry of all loaded workflow definitions."""

    _instance: "WorkflowRegistry | None" = None

    def __init__(self) -> None:
        self._workflows: dict[str, WorkflowDefinition] = {}

    @classmethod
    def get_instance(cls) -> "WorkflowRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Clear the singleton (useful in tests)."""
        cls._instance = None

    def load_all(self, workflows_dir: str | Path | None = None) -> None:
        """Load all workflow YAML files from the workflows directory."""
        wdir = Path(workflows_dir) if workflows_dir else WORKFLOWS_DIR

        if not wdir.exists():
            logger.warning("[registry] Workflows dir not found: %s", wdir)
            return

        for yaml_path in sorted(wdir.glob("*.yaml")):
            try:
                self._load_file(yaml_path)
            except Exception as e:
                logger.error("[registry] Failed to load %s: %s", yaml_path.name, e)

        if not self._workflows:
            logger.warning("[registry] No workflows loaded from %s", wdir)

    def _load_file(self, path: Path) -> None:
        """Load a single workflow YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        if not data:
            logger.warning("[registry] Empty workflow file: %s", path.name)
            return

        wf = WorkflowDefinition.from_dict(data)
        if wf.name in self._workflows:
            raise WorkflowError(
                f"Duplicate workflow name '{wf.name}' from {path.name}"
            )
        self._workflows[wf.name] = wf
        logger.info("[registry] Loaded workflow '%s' from %s", wf.name, path.name)

    def register(self, wf: WorkflowDefinition) -> None:
        """Programmatically register a workflow definition."""
        if wf.name in self._workflows:
            raise WorkflowError(f"Workflow '{wf.name}' already registered")
        self._workflows[wf.name] = wf

    def get(self, name: str | None = None) -> WorkflowDefinition:
        """Get a workflow by name. Defaults to 'coloring' for backward compat."""
        name = name or _DEFAULT_WORKFLOW
        wf = self._workflows.get(name)
        if wf is None:
            raise WorkflowError(
                f"Workflow '{name}' not found. Loaded: {list(self._workflows.keys())}"
            )
        return wf

    def list(self) -> list[str]:
        return list(self._workflows.keys())

    def has(self, name: str) -> bool:
        return name in self._workflows


# ── Convenience functions ────────────────────────────────────────────────────


def ensure_registry(workflows_dir: str | Path | None = None) -> WorkflowRegistry:
    """Get the registry singleton, loading workflows if not yet loaded."""
    reg = WorkflowRegistry.get_instance()
    if not reg._workflows:
        reg.load_all(workflows_dir)
    return reg


def get_workflow(name: str | None = None) -> WorkflowDefinition:
    """Get a workflow definition (convenience wrapper)."""
    return ensure_registry().get(name)
