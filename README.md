# NANDA Resolver

> **"DNS for AI agents."** Resolve a human-readable agent handle like
> `@acme:support/billing-bot` to a cryptographically verified endpoint and
> capability list — with no central trusted server beyond a lean index.

A runnable proof-of-concept of the core [Project NANDA](https://nanda.media.mit.edu/)
loop: **handle → signed AgentFacts → verified endpoint + capabilities**.

**Live demo:** https://nanda-resolver.onrender.com (free-tier — first request
after idle takes ~30s to wake the dyno).

```
@acme:support/billing-bot
           │
           ▼  (lookup)
    ┌──────────────┐
    │  lean index  │  ─►  factsUrl + operator public key
    └──────────────┘
           │
           ▼  (fetch)
    ┌──────────────┐
    │  AgentFacts  │  signed JSON-LD: endpoints, capabilities, TTL, proof
    └──────────────┘
           │
           ▼  (URDNA2015 canonicalize → Ed25519 verify → schema validate)
    ┌──────────────┐
    │  ✓ verified  │  endpoint + capabilities returned to the caller
    └──────────────┘
```

The index stores **only** the handle, facts URL, and operator public key — every
endpoint and capability lives in the signed AgentFacts document, in line with
the NANDA "lean core" principle.

---

## Table of contents

- [Why this exists](#why-this-exists)
- [Quickstart](#quickstart-under-15-minutes)
- [What you can do](#what-you-can-do)
- [What this POC proves](#what-this-poc-proves)
- [Architecture](#architecture)
- [How signing works](#how-signing-works)
- [Error taxonomy](#error-taxonomy)
- [Project layout](#project-layout)
- [Testing](#testing)
- [Deployment](#deployment)
- [Non-goals](#non-goals-explicitly-out-of-scope)
- [License](#license)

---

## Why this exists

As AI agents proliferate across vendors, there is no open, verifiable way to
discover *where* an agent lives and *trust* that it is who it claims to be.

An agent endpoint today is just a URL with no provenance — anyone can
impersonate it, capabilities are undocumented, and there is no cross-vendor
directory. Project NANDA proposes a "DNS for agents" to solve this, but the
concept is abstract until you can run it.

This POC makes it concrete: in under 15 minutes you can seed a directory of
nine sample agents, resolve any of them to a verified endpoint, query by
capability, and watch the resolver reject a tampered document in real time.

---

## Quickstart (under 15 minutes)

No external services. Python 3.10+ required.

```bash
git clone https://github.com/gkganesh12/NANDA_Resolver.git
cd NANDA_Resolver

python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Seed 9 sample agents (keypairs + signed AgentFacts + index.json)
nanda seed

# Start the resolver (FastAPI on http://127.0.0.1:8000)
nanda serve
```

In a second terminal:

```bash
nanda list
nanda resolve '@acme:support/billing-bot'
nanda discover --cap summarize-pdf
python -m scripts.tamper_demo
```

Open <http://127.0.0.1:8000/> in a browser for the web UI.

---

## What you can do

### Resolve a handle to a verified endpoint

```bash
$ nanda resolve '@acme:support/billing-bot'
✓ VERIFIED
endpoint     https://agents.acme.example/billing-bot
capabilities answer-billing-questions, refund-quote, summarize-pdf
operator     Acme, Inc.
ttl          3600s
```

If anything along the way is wrong — a flipped byte, a key mismatch, a schema
violation — you get a clear, distinct error and **no endpoint** is returned.

### Discover agents by capability

```bash
$ nanda discover --cap summarize-pdf
@acme:support/billing-bot
@paperstack/summarizer
@lawfirm/contract-review
```

Or via HTTP: `GET /discover?cap=summarize-pdf`.

### Watch the signature check do its job

```bash
$ python -m scripts.tamper_demo
1. Resolve the agent normally  → ✓ VERIFIED
2. Flip one byte in the signed AgentFacts file…
3. Resolve again              → ✗ verification_failed: signature does not match
4. Restore the file           → ✓ VERIFIED
```

---

## What this POC proves

| PRD requirement | How it's demonstrated |
|---|---|
| **P0.1** Lean index of 5–10 agents | `data/index.json` holds 9 entries; each entry has only `handle`, `factsUrl`, `operatorPublicKey` — verified by `test_index_contains_no_capability_data` |
| **P0.2** Signed AgentFacts (Ed25519 + URDNA2015) | `nanda/crypto.py`; W3C-style detached proof block. Signing canonicalizes via URDNA2015, hashes SHA-256, signs with Ed25519 |
| **P0.3** Resolver with signature + schema verification | `nanda/routers/resolver.py`. Returns `verification_failed` / `schema_failed` / `handle_mismatch` / 404 as distinct errors |
| **P0.4** Runnable in <15 min | `pip install -e .` → `nanda seed` → `nanda serve` → `nanda resolve` |
| **P1.1** Capability discovery | `nanda discover --cap <tag>` and `GET /discover?cap=<tag>` |
| **P1.2** Tamper-attack demo | `python -m scripts.tamper_demo` flips a byte, shows verification failure, restores |
| **P1.3** Web UI | Single static page at `/` — handle input with ✓/✗ badge + discover form |

---

## Architecture

A single FastAPI process exposes four **logically independent** routers — each
owns its own storage and could be split into its own service without
refactoring callers:

```
nanda/ (FastAPI app on :8000)
├── routers/index.py     /index/lookup/{handle}, /index/list
├── routers/facts.py     /facts/{agent_id}.jsonld
├── routers/resolver.py  /resolve/{handle}, /discover?cap=...
└── ui/index.html        served at /
```

The resolver calls the index and facts host **over HTTP** (not via in-process
imports), so the separation is structurally honest, not a function call
masquerading as a service boundary.

### Public HTTP endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/` | Web UI |
| `GET` | `/index/list` | List all index entries |
| `GET` | `/index/lookup/{handle}` | Look up one entry |
| `GET` | `/facts/{agent_id}.jsonld` | Serve a signed AgentFacts document |
| `GET` | `/resolve/{handle}` | Resolve + verify (the money endpoint) |
| `GET` | `/discover?cap={tag}` | Find handles matching a capability tag |

---

## How signing works

The signing flow follows the W3C Linked Data Proofs pattern, simplified:

1. Drop the `proof` field from the AgentFacts dict.
2. Run **URDNA2015** on the JSON-LD body → canonical N-Quads string.
3. SHA-256 hash the canonical bytes.
4. Ed25519-sign the hash with the operator's private key.
5. Attach a `proof` block: `{ proofType, verificationKey, signatureValue }`.

URDNA2015 makes the signature robust to whitespace, key order, and prefix
choices — any semantically equivalent JSON-LD produces the same signature.

The JSON-LD `@context` is bundled in the package
(`nanda/contexts/nanda-v1.jsonld`) and served by a local PyLD document loader,
so canonicalization never hits the network.

---

## Error taxonomy

The resolver returns distinct errors so a caller can tell *why* it failed:

| HTTP | `detail` prefix | Meaning |
|---|---|---|
| `404` | (plain text) | Handle not in the index |
| `422` | `schema_failed: ...` | AgentFacts doc doesn't match the schema |
| `422` | `handle_mismatch: ...` | Index pointed at facts for a different handle |
| `400` | `verification_failed: ...` | Signature or proof block invalid |
| `502` | `Upstream ...` | Couldn't reach the index or facts host |

---

## Project layout

```
.
├── nanda/
│   ├── app.py              FastAPI app wiring
│   ├── cli.py              `nanda` console script
│   ├── config.py           data dir + base URL config
│   ├── crypto.py           URDNA2015 + Ed25519 sign/verify
│   ├── schema.py           AgentFacts + IndexEntry JSON Schema
│   ├── contexts/
│   │   └── nanda-v1.jsonld JSON-LD @context (loaded locally, never fetched)
│   ├── routers/
│   │   ├── index.py
│   │   ├── facts.py
│   │   └── resolver.py
│   └── ui/index.html
├── scripts/
│   ├── seed.py             Generate keypairs + signed facts + index
│   └── tamper_demo.py      P1.2 demo
├── tests/
│   ├── test_crypto.py      Sign/verify roundtrip + 5 tamper rejection cases
│   └── test_resolver_e2e.py End-to-end via FastAPI TestClient
├── data/                   Created by `nanda seed`
│   ├── index.json
│   ├── facts/*.jsonld
│   └── keys/*.priv / *.pub
├── DEPLOYMENT.md           How to run this in production
├── PRD.md                  Product spec this POC implements
└── why.md                  Design rationale
```

---

## Testing

```bash
pytest -v
```

The suite covers:

- Sign / verify roundtrip
- Five distinct tamper cases (body byte flip, signature byte flip, swapped key,
  removed proof block, replayed signature on a different doc)
- End-to-end resolve flow against a live FastAPI `TestClient`
- Index-contains-no-capability-data invariant (P0.1)

---

## Deployment

See [`DEPLOYMENT.md`](./DEPLOYMENT.md) for production deployment — Docker,
`docker-compose`, Render / Railway / Fly.io, a Kubernetes sketch, nginx /
Caddy reverse-proxy configs, environment variables, a hardening checklist,
and a GitHub Actions CI workflow.

### Configuration at a glance

| Env var | Default | Purpose |
|---|---|---|
| `NANDA_DATA_DIR` | `./data` | Where `index.json`, `facts/`, and `keys/` are read from |
| `NANDA_BASE_URL` | `http://127.0.0.1:8000` | Public base URL used to build links to the facts host |

> **Important:** the `data/keys/*.priv` files committed in this repo are
> throwaway POC keys generated by `nanda seed`. **Do not** reuse them for any
> real signing. In production, generate fresh keys and mount them from a
> secret store.

---

## Non-goals (explicitly out of scope)

Mirrors the [PRD](./PRD.md):

- No Registry Quilt federation
- No live endpoint rotation / sub-second revocation
- No DID resolution or production PKI
- No MCP / A2A wiring
- No agent invocation

The TTL field is present in AgentFacts so a follow-on POC can drop in
TTL-based expiry / rotation without re-architecting.

---

## License

This project is a proof of concept. Choose a license before publishing
anything you intend others to depend on.
