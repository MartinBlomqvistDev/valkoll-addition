"""Config loading shared by the pipeline scripts."""

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load_config(path: Path = ROOT / "config.yaml") -> dict[str, Any]:
    """Load the YAML config.

    Args:
        path: Path to the config file.

    Returns:
        The parsed config as a dict.
    """
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve(relative: str) -> Path:
    """Resolve a config path relative to the project root."""
    return ROOT / relative
