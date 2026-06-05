"""URDNA2015 JSON-LD canonicalization + Ed25519 sign/verify for AgentFacts.

Signing flow (per W3C Linked Data Proofs pattern, simplified):
  1. Take the AgentFacts dict, drop the ``proof`` field.
  2. Run URDNA2015 normalization -> canonical N-Quads string.
  3. SHA-256 hash the canonical bytes.
  4. Ed25519-sign the hash with the operator's private key.
  5. Attach the proof block with base64 signature + public key.

Verification reverses the same steps deterministically.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
from importlib import resources
from pathlib import Path
from typing import Any

from nacl.exceptions import BadSignatureError
from nacl.signing import SigningKey, VerifyKey
from pyld import jsonld

PROOF_TYPE = "Ed25519Signature2025-URDNA2015"
CONTEXT_URL = "https://nanda.local/v1/context.jsonld"


class VerificationError(Exception):
    """Raised when an AgentFacts signature fails verification."""


# ---------------------------------------------------------------------------
# JSON-LD context loader: serve the nanda context from a bundled local file
# so the resolver never hits the network during canonicalization.
# ---------------------------------------------------------------------------

def _load_local_context() -> dict[str, Any]:
    with resources.files("nanda.contexts").joinpath("nanda-v1.jsonld").open("r") as fh:
        return json.load(fh)


_LOCAL_CONTEXT_CACHE: dict[str, Any] | None = None


def _nanda_document_loader(secure: bool = False, **kwargs: Any):
    """Return a PyLD-compatible document loader that resolves CONTEXT_URL locally."""

    def loader(url: str, options: dict[str, Any] | None = None) -> dict[str, Any]:
        global _LOCAL_CONTEXT_CACHE
        if url == CONTEXT_URL:
            if _LOCAL_CONTEXT_CACHE is None:
                _LOCAL_CONTEXT_CACHE = _load_local_context()
            return {
                "contextUrl": None,
                "documentUrl": url,
                "document": _LOCAL_CONTEXT_CACHE,
            }
        raise jsonld.JsonLdError(
            f"Refusing to fetch non-local JSON-LD context: {url}",
            "jsonld.LoadDocumentError",
        )

    return loader


jsonld.set_document_loader(_nanda_document_loader())


# ---------------------------------------------------------------------------
# Keypair helpers
# ---------------------------------------------------------------------------

def generate_keypair() -> tuple[str, str]:
    """Generate a new Ed25519 keypair. Returns (private_key_b64, public_key_b64)."""
    sk = SigningKey.generate()
    priv_b64 = base64.b64encode(bytes(sk)).decode("ascii")
    pub_b64 = base64.b64encode(bytes(sk.verify_key)).decode("ascii")
    return priv_b64, pub_b64


def write_keypair(operator_id: str, keys_dir: Path) -> tuple[str, str]:
    """Generate a keypair and persist it to keys_dir. Returns (priv_b64, pub_b64)."""
    keys_dir.mkdir(parents=True, exist_ok=True)
    priv_b64, pub_b64 = generate_keypair()
    (keys_dir / f"{operator_id}.priv").write_text(priv_b64 + "\n")
    (keys_dir / f"{operator_id}.pub").write_text(pub_b64 + "\n")
    return priv_b64, pub_b64


def load_private_key(operator_id: str, keys_dir: Path) -> str:
    return (keys_dir / f"{operator_id}.priv").read_text().strip()


def load_public_key(operator_id: str, keys_dir: Path) -> str:
    return (keys_dir / f"{operator_id}.pub").read_text().strip()


# ---------------------------------------------------------------------------
# Canonicalization + sign/verify
# ---------------------------------------------------------------------------

def canonicalize(doc_without_proof: dict[str, Any]) -> bytes:
    """URDNA2015-normalize a JSON-LD document and return canonical N-Quads bytes."""
    normalized = jsonld.normalize(
        doc_without_proof,
        {"algorithm": "URDNA2015", "format": "application/n-quads"},
    )
    return normalized.encode("utf-8")


def _digest(doc_without_proof: dict[str, Any]) -> bytes:
    return hashlib.sha256(canonicalize(doc_without_proof)).digest()


def sign_agent_facts(doc: dict[str, Any], private_key_b64: str) -> dict[str, Any]:
    """Return a copy of ``doc`` with a ``proof`` block attached."""
    body = copy.deepcopy(doc)
    body.pop("proof", None)

    sk = SigningKey(base64.b64decode(private_key_b64))
    pub_b64 = base64.b64encode(bytes(sk.verify_key)).decode("ascii")

    signature = sk.sign(_digest(body)).signature
    body["proof"] = {
        "proofType": PROOF_TYPE,
        "verificationKey": pub_b64,
        "signatureValue": base64.b64encode(signature).decode("ascii"),
    }
    return body


def verify_agent_facts(doc: dict[str, Any], expected_public_key_b64: str) -> None:
    """Verify the ``proof`` block on an AgentFacts doc.

    Raises VerificationError on any failure (missing proof, wrong key, bad signature).
    """
    proof = doc.get("proof")
    if not isinstance(proof, dict):
        raise VerificationError("AgentFacts document is missing a 'proof' block")

    if proof.get("proofType") != PROOF_TYPE:
        raise VerificationError(
            f"Unsupported proofType: {proof.get('proofType')!r} (expected {PROOF_TYPE!r})"
        )

    doc_key = proof.get("verificationKey")
    if doc_key != expected_public_key_b64:
        raise VerificationError(
            "AgentFacts verificationKey does not match the key recorded in the index"
        )

    try:
        sig = base64.b64decode(proof["signatureValue"], validate=True)
        pub = base64.b64decode(expected_public_key_b64, validate=True)
    except (KeyError, ValueError) as exc:
        raise VerificationError(f"Malformed proof material: {exc}") from exc

    body = copy.deepcopy(doc)
    body.pop("proof", None)

    try:
        VerifyKey(pub).verify(_digest(body), sig)
    except BadSignatureError as exc:
        raise VerificationError("Ed25519 signature is invalid (document tampered or wrong key)") from exc
