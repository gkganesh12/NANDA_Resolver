"""Facts host — serves signed AgentFacts JSON-LD documents.

This is intentionally dumb. It just streams the file. Verification is the
resolver's job; the facts host is untrusted by design.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from nanda.config import facts_dir

router = APIRouter(prefix="/facts", tags=["facts"])


@router.get("/{agent_id}.jsonld")
def get_facts(agent_id: str) -> JSONResponse:
    path = facts_dir() / f"{agent_id}.jsonld"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"AgentFacts not found: {agent_id}")
    return JSONResponse(
        content=json.loads(path.read_text()),
        media_type="application/ld+json",
    )
