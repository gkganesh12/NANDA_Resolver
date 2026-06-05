"""Seed the index with 9 sample agents, generating keypairs and signed AgentFacts.

Idempotent: re-running rebuilds everything from scratch (deletes existing data).
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nanda.config import base_url, facts_dir, index_path, keys_dir
from nanda.crypto import CONTEXT_URL, sign_agent_facts, write_keypair
from nanda.schema import validate_agent_facts, validate_index_entry


SAMPLE_AGENTS: list[dict[str, Any]] = [
    {
        "operator_id": "acme",
        "operator_name": "Acme Corp",
        "agent_id": "acme-billing-bot",
        "handle": "@acme:support/billing-bot",
        "endpoint": "https://acme.example/agents/billing",
        "protocol": "https+a2a",
        "capabilities": [
            ("answer-billing-question", "Answer customer billing questions"),
            ("issue-refund", "Issue a refund up to $500"),
        ],
    },
    {
        "operator_id": "acme",
        "operator_name": "Acme Corp",
        "agent_id": "acme-onboarding",
        "handle": "@acme:sales/onboarding",
        "endpoint": "https://acme.example/agents/onboarding",
        "protocol": "https+a2a",
        "capabilities": [
            ("schedule-demo", "Schedule a product demo"),
            ("send-welcome-email", "Send a templated welcome email"),
        ],
    },
    {
        "operator_id": "mercy-health",
        "operator_name": "Mercy Health Network",
        "agent_id": "mercy-intake-triage",
        "handle": "@mercy-health:clinic/intake-triage",
        "endpoint": "https://mercy.example/agents/triage",
        "protocol": "https+a2a",
        "capabilities": [
            ("triage-symptoms", "Assess symptom severity"),
            ("book-appointment", "Book a clinic appointment"),
        ],
    },
    {
        "operator_id": "first-bank",
        "operator_name": "First National Bank",
        "agent_id": "firstbank-fraud-alert",
        "handle": "@first-bank:security/fraud-alert",
        "endpoint": "https://firstbank.example/agents/fraud",
        "protocol": "https+a2a",
        "capabilities": [
            ("flag-transaction", "Flag a suspicious transaction"),
            ("freeze-card", "Temporarily freeze a card"),
        ],
    },
    {
        "operator_id": "paperstack",
        "operator_name": "PaperStack Labs",
        "agent_id": "paperstack-summarizer",
        "handle": "@paperstack:tools/pdf-summarizer",
        "endpoint": "https://paperstack.example/agents/summarize",
        "protocol": "https+mcp",
        "capabilities": [
            ("summarize-pdf", "Summarize a PDF document"),
            ("extract-citations", "Extract bibliographic citations"),
        ],
    },
    {
        "operator_id": "paperstack",
        "operator_name": "PaperStack Labs",
        "agent_id": "paperstack-translator",
        "handle": "@paperstack:tools/translator",
        "endpoint": "https://paperstack.example/agents/translate",
        "protocol": "https+mcp",
        "capabilities": [
            ("translate-text", "Translate text between languages"),
        ],
    },
    {
        "operator_id": "city-transit",
        "operator_name": "City Transit Authority",
        "agent_id": "transit-trip-planner",
        "handle": "@city-transit:public/trip-planner",
        "endpoint": "https://transit.example/agents/plan",
        "protocol": "https+a2a",
        "capabilities": [
            ("plan-trip", "Plan a multi-modal trip"),
            ("check-service-alerts", "Check current service disruptions"),
        ],
    },
    {
        "operator_id": "indie-dev",
        "operator_name": "Indie Dev Solo",
        "agent_id": "indie-recipe-bot",
        "handle": "@indie-dev:hobby/recipe-bot",
        "endpoint": "https://indie.example/agents/recipe",
        "protocol": "https+a2a",
        "capabilities": [
            ("suggest-recipe", "Suggest a recipe from ingredients"),
        ],
    },
    {
        "operator_id": "lawfirm-co",
        "operator_name": "Lawfirm & Co",
        "agent_id": "lawfirm-contract-review",
        "handle": "@lawfirm-co:legal/contract-review",
        "endpoint": "https://lawfirm.example/agents/contract",
        "protocol": "https+a2a",
        "capabilities": [
            ("summarize-pdf", "Summarize a contract PDF"),
            ("flag-risk-clause", "Flag risky contract clauses"),
        ],
    },
]


def _reset() -> None:
    for d in (facts_dir(), keys_dir()):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)
    if index_path().exists():
        index_path().unlink()


def _build_facts(agent: dict[str, Any]) -> dict[str, Any]:
    return {
        "@context": CONTEXT_URL,
        "type": "AgentFacts",
        "id": f"https://nanda.local/agents/{agent['agent_id']}",
        "handle": agent["handle"],
        "operatorName": agent["operator_name"],
        "endpoints": [
            {
                "endpointUrl": agent["endpoint"],
                "endpointProtocol": agent["protocol"],
            }
        ],
        "capabilities": [
            {"capabilityTag": tag, "capabilityDescription": desc}
            for tag, desc in agent["capabilities"]
        ],
        "ttl": 3600,
        "issuedAt": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    }


def main() -> None:
    _reset()

    operator_keys: dict[str, tuple[str, str]] = {}  # operator_id -> (priv, pub)
    entries: list[dict[str, Any]] = []

    for agent in SAMPLE_AGENTS:
        op_id = agent["operator_id"]
        if op_id not in operator_keys:
            operator_keys[op_id] = write_keypair(op_id, keys_dir())
        priv_b64, pub_b64 = operator_keys[op_id]

        facts = _build_facts(agent)
        signed = sign_agent_facts(facts, priv_b64)
        validate_agent_facts(signed)

        facts_path = facts_dir() / f"{agent['agent_id']}.jsonld"
        facts_path.write_text(json.dumps(signed, indent=2) + "\n")

        entry = {
            "handle": agent["handle"],
            "factsUrl": f"{base_url()}/facts/{agent['agent_id']}.jsonld",
            "operatorPublicKey": pub_b64,
        }
        validate_index_entry(entry)
        entries.append(entry)

    index_path().write_text(json.dumps({"entries": entries}, indent=2) + "\n")

    print(f"Seeded {len(entries)} agents:")
    for e in entries:
        print(f"  {e['handle']:<45}  -> {e['factsUrl']}")
    print(f"\nIndex: {index_path()}")
    print(f"Facts: {facts_dir()}")
    print(f"Keys:  {keys_dir()}")


if __name__ == "__main__":
    main()
