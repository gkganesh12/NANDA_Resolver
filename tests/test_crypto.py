"""Sign/verify and tamper-rejection tests for nanda.crypto."""
from __future__ import annotations

import copy

import pytest

from nanda.crypto import (
    CONTEXT_URL,
    VerificationError,
    generate_keypair,
    sign_agent_facts,
    verify_agent_facts,
)


def _sample_facts() -> dict:
    return {
        "@context": CONTEXT_URL,
        "type": "AgentFacts",
        "id": "https://nanda.local/agents/acme-billing",
        "handle": "@acme:support/billing-bot",
        "operatorName": "Acme Corp",
        "endpoints": [
            {"endpointUrl": "https://acme.example/agents/billing", "endpointProtocol": "https"}
        ],
        "capabilities": [
            {"capabilityTag": "answer-billing-question", "capabilityDescription": "..."},
        ],
        "ttl": 3600,
        "issuedAt": "2026-06-05T00:00:00Z",
    }


def test_sign_then_verify_roundtrip():
    priv, pub = generate_keypair()
    signed = sign_agent_facts(_sample_facts(), priv)
    assert signed["proof"]["verificationKey"] == pub
    verify_agent_facts(signed, pub)  # must not raise


def test_verify_rejects_tampered_body():
    priv, pub = generate_keypair()
    signed = sign_agent_facts(_sample_facts(), priv)

    tampered = copy.deepcopy(signed)
    # flip the endpoint URL — classic impersonation attempt
    tampered["endpoints"][0]["endpointUrl"] = "https://attacker.example/agents/billing"

    with pytest.raises(VerificationError, match="signature is invalid"):
        verify_agent_facts(tampered, pub)


def test_verify_rejects_tampered_capabilities():
    priv, pub = generate_keypair()
    signed = sign_agent_facts(_sample_facts(), priv)

    tampered = copy.deepcopy(signed)
    tampered["capabilities"].append(
        {"capabilityTag": "drain-bank-account", "capabilityDescription": "evil"}
    )

    with pytest.raises(VerificationError):
        verify_agent_facts(tampered, pub)


def test_verify_rejects_swapped_public_key():
    priv_a, _pub_a = generate_keypair()
    _priv_b, pub_b = generate_keypair()
    signed = sign_agent_facts(_sample_facts(), priv_a)

    with pytest.raises(VerificationError, match="does not match"):
        verify_agent_facts(signed, pub_b)


def test_verify_rejects_missing_proof():
    facts = _sample_facts()
    with pytest.raises(VerificationError, match="missing a 'proof' block"):
        verify_agent_facts(facts, "anything")


def test_verify_rejects_wrong_proof_type():
    priv, pub = generate_keypair()
    signed = sign_agent_facts(_sample_facts(), priv)
    signed["proof"]["proofType"] = "SomethingElse"
    with pytest.raises(VerificationError, match="Unsupported proofType"):
        verify_agent_facts(signed, pub)
