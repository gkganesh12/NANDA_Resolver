"""AgentFacts JSON Schema and validation."""
from __future__ import annotations

from typing import Any

import jsonschema

AGENT_FACTS_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "AgentFacts",
    "type": "object",
    "required": [
        "@context",
        "type",
        "id",
        "handle",
        "operatorName",
        "endpoints",
        "capabilities",
        "ttl",
        "issuedAt",
        "proof",
    ],
    "properties": {
        "@context": {
            "oneOf": [
                {"type": "string"},
                {"type": "array"},
                {"type": "object"},
            ]
        },
        "type": {"const": "AgentFacts"},
        "id": {"type": "string", "minLength": 1},
        "handle": {
            "type": "string",
            "pattern": r"^@[a-z0-9-]+:[a-z0-9-]+(/[a-z0-9-]+)*$",
        },
        "operatorName": {"type": "string", "minLength": 1},
        "endpoints": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["endpointUrl", "endpointProtocol"],
                "properties": {
                    "endpointUrl": {"type": "string", "format": "uri"},
                    "endpointProtocol": {"type": "string", "minLength": 1},
                },
                "additionalProperties": False,
            },
        },
        "capabilities": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["capabilityTag", "capabilityDescription"],
                "properties": {
                    "capabilityTag": {
                        "type": "string",
                        "pattern": r"^[a-z0-9-]+$",
                    },
                    "capabilityDescription": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        "ttl": {"type": "integer", "minimum": 0},
        "issuedAt": {"type": "string", "format": "date-time"},
        "proof": {
            "type": "object",
            "required": [
                "proofType",
                "verificationKey",
                "signatureValue",
            ],
            "properties": {
                "proofType": {"const": "Ed25519Signature2025-URDNA2015"},
                "verificationKey": {"type": "string", "minLength": 1},
                "signatureValue": {"type": "string", "minLength": 1},
            },
            "additionalProperties": False,
        },
    },
    "additionalProperties": False,
}


INDEX_ENTRY_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "IndexEntry",
    "type": "object",
    "required": ["handle", "factsUrl", "operatorPublicKey"],
    "properties": {
        "handle": {
            "type": "string",
            "pattern": r"^@[a-z0-9-]+:[a-z0-9-]+(/[a-z0-9-]+)*$",
        },
        "factsUrl": {"type": "string", "format": "uri"},
        "operatorPublicKey": {"type": "string", "minLength": 1},
    },
    "additionalProperties": False,
}


class SchemaError(Exception):
    """Raised when a document fails schema validation."""


def validate_agent_facts(doc: dict[str, Any]) -> None:
    """Validate an AgentFacts dict. Raises SchemaError on failure."""
    try:
        jsonschema.validate(instance=doc, schema=AGENT_FACTS_SCHEMA)
    except jsonschema.ValidationError as exc:
        raise SchemaError(f"AgentFacts schema validation failed: {exc.message}") from exc


def validate_index_entry(entry: dict[str, Any]) -> None:
    """Validate a single index entry. Raises SchemaError on failure."""
    try:
        jsonschema.validate(instance=entry, schema=INDEX_ENTRY_SCHEMA)
    except jsonschema.ValidationError as exc:
        raise SchemaError(f"Index entry schema validation failed: {exc.message}") from exc
