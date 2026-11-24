"""Shared fixtures. Pipeline steps have numeric file names, so they are loaded by path."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_step(name: str) -> ModuleType:
    """Import a pipeline script as a module.

    Args:
        name: File name in pipeline/ without extension, e.g. "02_clean_dedup".

    Returns:
        The loaded module.
    """
    path = ROOT / "pipeline" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"step_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def step():
    """Return the step loader."""
    return load_step
