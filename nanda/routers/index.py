"""Index router — the lean directory of handle -> (facts_url, operator pubkey).

By design this router stores **no** endpoint or capability data; it only points
callers at the AgentFacts document and supplies the public key needed to verify it.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException

from nanda.config import index_path
from nanda.schema import SchemaError, validate_index_entry

router = APIRouter(prefix="/index", tags=["index"])


def _load_index() -> dict[str, dict[str, Any]]:
    path = index_path()
    if not path.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Index not seeded. Run `python -m scripts.seed` first.",
        )
    raw = json.loads(path.read_text())
    if not isinstance(raw, dict) or "entries" not in raw:
        raise HTTPException(status_code=500, detail="Malformed index file")

    out: dict[str, dict[str, Any]] = {}
    for entry in raw["entries"]:
        try:
            validate_index_entry(entry)
        except SchemaError as exc:
            raise HTTPException(status_code=500, detail=f"Corrupt index entry: {exc}")
        out[entry["handle"]] = entry
    return out


@router.get("/lookup/{handle:path}")
def lookup(handle: str) -> dict[str, Any]:
    """Return the index entry for an exact handle, or 404."""
    entries = _load_index()
    entry = entries.get(handle)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Handle not found: {handle}")
    return entry


@router.get("/list")
def list_all() -> dict[str, Any]:
    """List all handles registered in the index (handle + facts_url only)."""
    entries = _load_index()
    return {
        "count": len(entries),
        "handles": sorted(entries.keys()),
    }
