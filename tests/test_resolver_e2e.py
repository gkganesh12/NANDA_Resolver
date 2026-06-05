"""End-to-end tests: spin up the FastAPI app in-process and drive it with TestClient.

Each test gets a fresh data dir seeded by scripts.seed, so they're isolated.
"""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def seeded_app(tmp_path: Path, monkeypatch):
    """Spin up the app with a fresh data dir and pre-seeded sample agents."""
    monkeypatch.setenv("NANDA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("NANDA_BASE_URL", "http://testserver")

    # Reload config so the env vars take effect, then reload modules that captured paths.
    import nanda.config
    importlib.reload(nanda.config)
    import nanda.routers.index as index_mod
    import nanda.routers.facts as facts_mod
    import nanda.routers.resolver as resolver_mod
    importlib.reload(index_mod)
    importlib.reload(facts_mod)
    importlib.reload(resolver_mod)
    import nanda.app as app_mod
    importlib.reload(app_mod)

    from scripts import seed
    importlib.reload(seed)
    seed.main()

    client = TestClient(app_mod.app)

    # Patch the resolver's httpx client so internal /index and /facts calls
    # are dispatched in-process by the TestClient instead of hitting localhost.
    import httpx
    orig_client = httpx.Client

    class InProcessClient:
        def __init__(self, *a, **kw):
            self._client = client
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url, **kw):
            # Strip the base URL prefix; TestClient takes paths.
            path = url.replace("http://testserver", "", 1)
            return self._client.get(path)

    monkeypatch.setattr("nanda.routers.resolver.httpx.Client", InProcessClient)

    yield client


def test_list_returns_nine_handles(seeded_app):
    r = seeded_app.get("/index/list")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 9
    assert "@acme:support/billing-bot" in body["handles"]


def test_resolve_happy_path(seeded_app):
    r = seeded_app.get("/resolve/@acme:support/billing-bot")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verified"] is True
    assert body["operator"] == "Acme Corp"
    assert body["endpoints"][0]["endpointUrl"] == "https://acme.example/agents/billing"
    tags = {c["capabilityTag"] for c in body["capabilities"]}
    assert "answer-billing-question" in tags


def test_resolve_unknown_handle_returns_404(seeded_app):
    r = seeded_app.get("/resolve/@nonexistent:foo/bar")
    assert r.status_code == 404


def test_resolve_rejects_tampered_facts(seeded_app, tmp_path):
    facts_file = tmp_path / "facts" / "acme-billing-bot.jsonld"
    doc = json.loads(facts_file.read_text())
    doc["endpoints"][0]["endpointUrl"] = "https://attacker.example/steal"
    facts_file.write_text(json.dumps(doc))

    r = seeded_app.get("/resolve/@acme:support/billing-bot")
    assert r.status_code == 400, r.text
    assert "verification_failed" in r.json()["detail"]


def test_resolve_rejects_handle_mismatch(seeded_app, tmp_path):
    """Sneaky: an attacker swaps the facts file at the URL the index points to."""
    real = tmp_path / "facts" / "acme-billing-bot.jsonld"
    other = tmp_path / "facts" / "indie-recipe-bot.jsonld"
    real.write_text(other.read_text())

    r = seeded_app.get("/resolve/@acme:support/billing-bot")
    assert r.status_code == 422, r.text
    assert "handle_mismatch" in r.json()["detail"]


def test_discover_finds_shared_capability(seeded_app):
    """summarize-pdf is declared by both paperstack and lawfirm-co agents."""
    r = seeded_app.get("/discover?cap=summarize-pdf")
    assert r.status_code == 200, r.text
    body = r.json()
    handles = {m["handle"] for m in body["matches"]}
    assert handles == {
        "@paperstack:tools/pdf-summarizer",
        "@lawfirm-co:legal/contract-review",
    }


def test_discover_empty_for_unknown_capability(seeded_app):
    r = seeded_app.get("/discover?cap=nonexistent-capability")
    assert r.status_code == 200
    assert r.json()["matches"] == []


def test_all_nine_agents_resolve(seeded_app):
    """PRD success metric: 100% of seeded handles resolve successfully."""
    handles = seeded_app.get("/index/list").json()["handles"]
    assert len(handles) == 9
    for h in handles:
        r = seeded_app.get(f"/resolve/{h}")
        assert r.status_code == 200, f"{h} failed: {r.text}"
        assert r.json()["verified"] is True


def test_index_contains_no_capability_data(seeded_app, tmp_path):
    """NANDA 'minimal core' principle: index has no endpoint/capability data."""
    index_file = tmp_path / "index.json"
    raw = json.loads(index_file.read_text())
    for entry in raw["entries"]:
        assert set(entry.keys()) == {"handle", "factsUrl", "operatorPublicKey"}
