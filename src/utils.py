"""Shared utilities for file I/O, YAML handling, and validation."""

import os
import yaml

# ---------------------------------------------------------------------------
# Sentinel strings written by comparator and read back by executor.
# Single source of truth — changing here fixes both sides automatically.
# ---------------------------------------------------------------------------
NO_ELEMENT_DIFF = "NO DIFFERENCES IN REGARDS TO ELEMENT NAMES"
NO_REQ_DIFF = "NO DIFFERENCES IN REGARDS TO ELEMENT REQUIREMENTS"


def validate_file_exists(path: str) -> None:
    """Raise FileNotFoundError if path does not exist as a regular file."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path}")


def validate_path_exists(path: str) -> None:
    """Raise FileNotFoundError if path does not exist (file or directory)."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Path not found: {path}")


def validate_extension(path: str, ext: str) -> None:
    """Raise ValueError if path does not end with the given extension."""
    if not path.lower().endswith(ext.lower()):
        raise ValueError(f"Expected a {ext} file, got: {path}")


def ensure_dir(path: str) -> None:
    """Create directory (and parents) if it does not exist."""
    os.makedirs(path, exist_ok=True)


def load_yaml(path: str) -> dict:
    """Load and return a YAML file as a Python dict."""
    validate_file_exists(path)
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        return {}
    return data


def save_yaml(data: dict, path: str) -> None:
    """Serialize a dict to YAML and write it to path."""
    ensure_dir(os.path.dirname(path) or ".")
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


def write_text(content: str, path: str) -> None:
    """Write (overwrite) content to a text file."""
    ensure_dir(os.path.dirname(path) or ".")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def append_text(content: str, path: str) -> None:
    """Append content to a text file (creates if not present)."""
    ensure_dir(os.path.dirname(path) or ".")
    with open(path, "a", encoding="utf-8") as f:
        f.write(content)
