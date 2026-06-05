"""Live tamper-attack demo, exposed as an HTTP endpoint for the web UI.

POST /demo/tamper-attack {"handle": "..."}

Cycle:
  1. Resolve cleanly (expect ✓).
  2. Modify the on-disk AgentFacts file — swap endpoint to attacker URL.
  3. Resolve again (expect ✗ verification_failed).
  4. Restore the original file (expect ✓).

Returns a structured trace the UI animates through.
"""
from __future__ import annotations

import json
import shutil
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from nanda.config import base_url, facts_dir

router = APIRouter(prefix="/demo", tags=["demo"])

ATTACKER_URL = "https://attacker.example/steal-billing-data"


class TamperRequest(BaseModel):
    handle: str


def _http_get(url: str) -> tuple[int, Any]:
    with httpx.Client(timeout=5.0) as c:
        r = c.get(url)
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text}
    return r.status_code, body


def _agent_id_for(handle: str) -> str:
    """Look up the AgentFacts file id by handle (via the index)."""
    status, body = _http_get(f"{base_url()}/index/lookup/{handle}")
    if status != 200:
        raise HTTPException(status_code=status, detail=body)
    facts_url = body["factsUrl"]
    name = urlparse(facts_url).path.rsplit("/", 1)[-1]
    if name.endswith(".jsonld"):
        name = name[: -len(".jsonld")]
    return name


@router.post("/tamper-attack")
def tamper_attack(req: TamperRequest) -> dict[str, Any]:
    handle = req.handle
    agent_id = _agent_id_for(handle)

    facts_path = facts_dir() / f"{agent_id}.jsonld"
    if not facts_path.exists():
        raise HTTPException(status_code=404, detail=f"Facts file missing: {facts_path}")

    backup_path = facts_path.with_suffix(".jsonld.bak")
    shutil.copy(facts_path, backup_path)

    trace: list[dict[str, Any]] = []
    try:
        # 1. Clean resolve.
        status, body = _http_get(f"{base_url()}/resolve/{handle}")
        original_endpoint = (
            body.get("endpoints", [{}])[0].get("endpointUrl") if status == 200 else None
        )
        trace.append(
            {
                "phase": "before",
                "title": "Resolve untampered AgentFacts",
                "status": status,
                "verified": status == 200,
                "endpoint": original_endpoint,
                "detail": None if status == 200 else body.get("detail"),
            }
        )

        # 2. Tamper.
        doc = json.loads(facts_path.read_text())
        doc["endpoints"][0]["endpointUrl"] = ATTACKER_URL
        facts_path.write_text(json.dumps(doc, indent=2) + "\n")
        trace.append(
            {
                "phase": "tamper",
                "title": "Attacker rewrites endpoint in signed AgentFacts file",
                "originalEndpoint": original_endpoint,
                "tamperedEndpoint": ATTACKER_URL,
                "note": "Signature was NOT updated — the operator's private key isn't available.",
            }
        )

        # 3. Resolve tampered.
        status, body = _http_get(f"{base_url()}/resolve/{handle}")
        trace.append(
            {
                "phase": "after",
                "title": "Resolve tampered AgentFacts",
                "status": status,
                "verified": status == 200,
                "detail": body.get("detail") if status != 200 else None,
            }
        )
    finally:
        # 4. Always restore.
        shutil.move(backup_path, facts_path)

    status, body = _http_get(f"{base_url()}/resolve/{handle}")
    trace.append(
        {
            "phase": "restored",
            "title": "Restore original file — verification passes again",
            "status": status,
            "verified": status == 200,
            "endpoint": body.get("endpoints", [{}])[0].get("endpointUrl") if status == 200 else None,
        }
    )

    return {"handle": handle, "agentId": agent_id, "trace": trace}
