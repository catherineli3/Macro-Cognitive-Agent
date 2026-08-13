"""Configuration loader — reads configs/*.yaml files.

Single source of configuration: configs/ directory with YAML files.
Environment variables override for secrets (DB URL, API keys).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# Load .env file before anything else
try:
    from dotenv import load_dotenv

    _ENV_PATH = Path(__file__).parent.parent.parent / ".env"
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH)
except ImportError:
    pass

from src.shared.exceptions import ConfigurationError

# Default config directory relative to project root
_CONFIG_DIR = Path(__file__).parent.parent.parent / "configs"


def load_yaml(filename: str, config_dir: Path | None = None) -> dict[str, Any]:
    """Load a YAML configuration file.

    Args:
        filename: Config file name, e.g. 'settings.yaml'.
        config_dir: Optional override for config directory.

    Returns:
        Parsed YAML as dict.

    Raises:
        ConfigurationError: If file not found or YAML is invalid.
    """
    directory = config_dir or _CONFIG_DIR
    path = directory / filename
    if not path.exists():
        raise ConfigurationError(f"Config file not found: {path}")
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Invalid YAML in {path}: {exc}") from exc


def get_database_url() -> str:
    """Get the database URL, preferring env var over config file.

    Priority:
        1. DATABASE_URL environment variable
        2. configs/settings.yaml → database.url
    """
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url

    settings = load_yaml("settings.yaml")
    url = settings.get("database", {}).get("url")
    if not url:
        raise ConfigurationError("No DATABASE_URL found in environment or settings.yaml")
    return url


def get_settings() -> dict[str, Any]:
    """Load full application settings from settings.yaml."""
    return load_yaml("settings.yaml")
