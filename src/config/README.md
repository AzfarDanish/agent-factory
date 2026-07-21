# Config — Configuration Loader

Loads configuration from YAML files, environment variables, and CLI overrides.

## How It Works

1. Load `config/defaults.yaml` as the base
2. Override with environment-specific YAML if `FACTORY_ENV` is set
3. Override with environment variables (`FACTORY_SECTION_KEY`)
4. Override with CLI arguments

The `loader.py` module returns a typed config dict with all values validated.
