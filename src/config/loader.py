"""Configuration loader — reads YAML + env vars + CLI overrides.

Precedence (highest to lowest):
1. CLI flags
2. Environment variables (FACTORY_SECTION_KEY)
3. Environment-specific YAML ($FACTORY_ENV.yaml)
4. config/defaults.yaml
"""

import os
import os.path
from pathlib import Path
from typing import Any

import yaml


# Root of the project (where config/ lives)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"


class ConfigError(Exception):
    """Raised when config loading fails."""


def _env_to_key(env_name: str) -> tuple[str, ...]:
    """Convert FACTORY_QUEUE_BACKEND to ('queue_backend',)."""
    parts = env_name.lower().replace("factory_", "", 1).split("_", 1)
    if len(parts) == 1:
        return (parts[0],)
    return tuple(parts)


def _deep_set(d: dict, keys: tuple[str, ...], value: Any) -> None:
    """Set a nested dict value from key tuple."""
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = value


def _deep_get(d: dict, keys: tuple[str, ...], default: Any = None) -> Any:
    """Get a nested dict value from key tuple."""
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k)
            if d is None:
                return default
        else:
            return default
    return d


def load_config(env: str | None = None) -> dict[str, Any]:
    """Load and merge configuration from all sources.

    Args:
        env: Environment name (development, production). Falls back to FACTORY_ENV.

    Returns:
        Merged config dict.
    """
    config: dict[str, Any] = {}

    # 1. Load defaults.yaml
    defaults_path = CONFIG_DIR / "defaults.yaml"
    if defaults_path.exists():
        with open(defaults_path) as f:
            config = yaml.safe_load(f) or {}

    # 2. Load all config/*.yaml files (overlay)
    for yaml_file in sorted(CONFIG_DIR.glob("*.yaml")):
        if yaml_file.name == "defaults.yaml":
            continue
        with open(yaml_file) as f:
            overlay = yaml.safe_load(f) or {}
            _deep_merge(config, overlay)

    # 3. Environment-specific overlay
    env = env or os.environ.get("FACTORY_ENV")
    if env:
        env_path = CONFIG_DIR / f"{env}.yaml"
        if env_path.exists():
            with open(env_path) as f:
                overlay = yaml.safe_load(f) or {}
                _deep_merge(config, overlay)

    # 4. Environment variables (FACTORY_*)
    for env_name, value in os.environ.items():
        if env_name.startswith("FACTORY_"):
            keys = _env_to_key(env_name)
            _deep_set(config, keys, _coerce_value(value))

    return config


def _coerce_value(value: str) -> Any:
    """Coerce env var string to bool/int/float if possible."""
    if value.lower() in ("true", "yes", "1"):
        return True
    if value.lower() in ("false", "no", "0"):
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def _deep_merge(base: dict, overlay: dict) -> None:
    """Recursively merge overlay into base dict."""
    for key, value in overlay.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def get_queue_config(config: dict) -> dict:
    """Extract queue configuration from the full config."""
    return config.get("queues", {})


def get_worker_config(config: dict, worker_name: str) -> dict:
    """Extract a specific worker's configuration."""
    workers = config.get("workers", {})
    return workers.get(worker_name, {})


def get_api_config(config: dict, api_name: str) -> dict:
    """Extract API configuration."""
    apis = config.get("apis", {})
    return apis.get(api_name, {})
