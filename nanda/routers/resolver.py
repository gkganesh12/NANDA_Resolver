"""Resolver — handle -> verified endpoint + capabilities.

Crucially, this router talks to the index and facts host **over HTTP**, not
via in-process function calls. That keeps the architectural separation real:
in a future deployment, those routes can move to other hosts unchanged.
"""
from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query

from nanda.config import base_url
from nanda.crypto import VerificationError, verify_agent_facts
from nanda.schema import SchemaError, validate_agent_facts

router = APIRouter(tags=["resolver"])


def _http_get(url: str) -> Any:
    try:
        with httpx.Client(timeout=5.0) as client:
            r = client.get(url)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Upstream fetch failed: {exc}") from exc
    if r.status_code == 404:
        raise HTTPException(status_code=404, detail=f"Not found at {url}")
    if r.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Upstream {r.status_code}: {r.text}")
    return r.json()


def _resolve_one(handle: str) -> dict[str, Any]:
    """Internal: full resolve pipeline. Returns the verified result envelope."""
    entry = _http_get(f"{base_url()}/index/lookup/{handle}")

    facts = _http_get(entry["factsUrl"])

    # Schema first — cheap, gives a clear error before we try to verify a malformed doc.
    try:
        validate_agent_facts(facts)
    except SchemaError as exc:
        raise HTTPException(status_code=422, detail=f"schema_failed: {exc}") from exc

    # Cross-check: the handle in the facts doc must match the handle that named it.
    if facts.get("handle") != handle:
        raise HTTPException(
            status_code=422,
            detail=f"handle_mismatch: index pointed to facts for {facts.get('handle')!r}",
        )

    try:
        verify_agent_facts(facts, entry["operatorPublicKey"])
    except VerificationError as exc:
        raise HTTPException(status_code=400, detail=f"verification_failed: {exc}") from exc

    return {
        "handle": handle,
        "verified": True,
        "operator": facts["operatorName"],
        "endpoints": facts["endpoints"],
        "capabilities": facts["capabilities"],
        "ttl": facts["ttl"],
        "issuedAt": facts["issuedAt"],
        "factsUrl": entry["factsUrl"],
        "proof": facts["proof"],
    }


@router.get("/resolve/{handle:path}")
def resolve(handle: str) -> dict[str, Any]:
    return _resolve_one(handle)


@router.get("/directory")
def directory() -> dict[str, Any]:
    """Return a verified summary of every agent in the index, in one call.

    Used by the web UI to render the directory cards without N round trips.
    Any agent whose verification fails is reported under 'rejected' rather
    than included in the verified list.
    """
    all_handles = _http_get(f"{base_url()}/index/list")["handles"]
    agents: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for handle in all_handles:
        try:
            agents.append(_resolve_one(handle))
        except HTTPException as exc:
            rejected.append({"handle": handle, "reason": str(exc.detail)})
    return {"agents": agents, "rejected": rejected, "count": len(agents)}


@router.get("/discover")
def discover(cap: str = Query(..., description="Capability tag to search for")) -> dict[str, Any]:
    """Return all handles whose AgentFacts declare the given capability tag.

    Each match is fully verified before being included — an agent with a broken
    signature is excluded with its handle reported under 'rejected'.
    """
    all_handles = _http_get(f"{base_url()}/index/list")["handles"]

    matches: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []

    for handle in all_handles:
        try:
            result = _resolve_one(handle)
        except HTTPException as exc:
            rejected.append({"handle": handle, "reason": str(exc.detail)})
            continue
        tags = {c["capabilityTag"] for c in result["capabilities"]}
        if cap in tags:
            matches.append(
                {
                    "handle": handle,
                    "operator": result["operator"],
                    "endpoints": result["endpoints"],
                    "matchedCapability": cap,
                }
            )

    return {"capability": cap, "matches": matches, "rejected": rejected}
