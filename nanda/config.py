"""Runtime configuration paths for the NANDA POC."""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    return Path(os.environ.get("NANDA_DATA_DIR", REPO_ROOT / "data"))


def facts_dir() -> Path:
    return data_dir() / "facts"


def keys_dir() -> Path:
    return data_dir() / "keys"


def index_path() -> Path:
    return data_dir() / "index.json"


def base_url() -> str:
    return os.environ.get("NANDA_BASE_URL", "http://127.0.0.1:8000")
