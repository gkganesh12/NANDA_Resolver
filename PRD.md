# PRD: NANDA Agent "Business Card" Resolver (POC)

**Status:** Draft v1 — Proof of Concept
**Owner:** TBD
**Target effort:** ~1 weekend / single sprint
**Last updated:** June 5, 2026

---

## Problem Statement

As AI agents proliferate across vendors and platforms, there is no open, verifiable way to discover *where* an agent lives and *trust* that it is who it claims to be. Today an agent endpoint is just a URL with no provenance — anyone can impersonate it, capabilities are undocumented, and there is no cross-vendor directory. Project NANDA proposes a "DNS for agents" to solve this, but the concept is abstract and hard to evaluate without something runnable. This POC makes the core NANDA loop — *handle → signed AgentFacts → verified endpoint + capabilities* — concrete and demonstrable.

## Goals

1. **Prove the resolution loop end-to-end**: a caller can resolve a human-friendly handle to a verified endpoint in a single command, with no central trusted server beyond a lean index.
2. **Demonstrate cryptographic trust**: every AgentFacts document is Ed25519-signed, and the resolver rejects any tampered or unsigned document.
3. **Make capabilities machine-discoverable**: a caller can read structured, schema-validated capability assertions from AgentFacts without contacting the agent.
4. **Be reproducible in a weekend**: a developer can clone, run, and demo the whole thing in under 15 minutes with no external dependencies.
5. **Stay faithful to NANDA's design**: index stays minimal/lean; endpoint + capability detail lives in AgentFacts (the index just points to it).

## Non-Goals

1. **The Registry Quilt / federation** — no CRDT sync, gossip, or multi-registry merging. Single index only. (Separate, heavier POC.)
2. **Actually invoking the agents** — the resolver returns a verified endpoint; it does not call the agent or proxy traffic. (Keeps scope to discovery + trust.)
3. **TTL-based endpoint rotation / sub-second revocation** — AgentFacts will carry a TTL field for realism, but live rotation is out of scope for v1. (Good candidate for a follow-on demo.)
4. **Production identity infrastructure** — no DID resolution, no PKI, no CA hierarchy. Keys are self-managed local files. (POC trust model, not production.)
5. **MCP/A2A protocol bridging** — we model capabilities NANDA-style but do not wire to real MCP servers. (Separate POC.)

## User Stories

**Agent operator (publishes an agent)**
- As an agent operator, I want to register my agent under a readable handle (e.g. `@acme:support/billing-bot`) so that others can find it by name instead of a raw URL.
- As an agent operator, I want to sign my AgentFacts with my private key so that consumers can verify the document genuinely came from me.
- As an agent operator, I want to declare my agent's capabilities in a structured schema so that consumers can filter for what I offer.

**Agent consumer (resolves an agent)**
- As a consumer, I want to pass a handle to the resolver and get back a verified endpoint and capability list so that I know where to connect and what the agent can do.
- As a consumer, I want the resolver to reject a tampered or wrongly-signed AgentFacts document so that I am protected from impersonation.
- As a consumer, I want to query agents by capability (e.g. "can summarize PDFs") so that I can discover relevant agents without knowing their handles in advance.

**Demo operator (shows the POC)**
- As a demo operator, I want a scripted "tamper attack" path so that I can visibly show the signature check failing in real time.

## Requirements

### Must-Have (P0)

**P0.1 — Lean index of 5–10 agents**
A minimal index mapping handles to a `FactsURL` (where the AgentFacts doc is served) plus the operator's public key and an AgentFacts signature reference. The index itself stores *no* capability or endpoint detail — only the pointer and verification material.
- [ ] Index seeded with 5–10 distinct agents under readable handles
- [ ] Each entry contains: handle, FactsURL, operator public key (or key reference), signature
- [ ] Index is queryable by exact handle
- [ ] Index contains no endpoint or capability data itself (NANDA "minimal core" principle)

**P0.2 — Signed AgentFacts documents**
Each agent has a JSON-LD AgentFacts document containing identity, operator, endpoint(s), and capabilities, signed with Ed25519.
- [ ] AgentFacts follows a documented, schema-validated structure (JSON-LD)
- [ ] Document includes: agent id/handle, operator name, endpoint(s), capability list, TTL field, signature
- [ ] Document is signed with the operator's Ed25519 private key
- [ ] A signing script generates a valid signed doc from plaintext + private key

**P0.3 — Resolver with signature verification**
Given a handle, the resolver fetches AgentFacts, verifies the Ed25519 signature against the index's public key, validates the schema, and returns endpoint + capabilities.
- Given a valid, untampered AgentFacts doc
- When a consumer resolves its handle
- Then the resolver returns the verified endpoint and capability list

- Given an AgentFacts doc whose body has been modified after signing
- When a consumer resolves its handle
- Then the resolver rejects it and returns a clear verification-failure error (and does NOT return the endpoint)

- [ ] Resolver takes a handle as input (CLI or simple API)
- [ ] Resolver looks up the FactsURL in the index
- [ ] Resolver fetches and parses the AgentFacts JSON-LD
- [ ] Resolver verifies the Ed25519 signature against the index public key
- [ ] Resolver validates the AgentFacts against the schema
- [ ] On success: returns endpoint(s) + capabilities
- [ ] On any failure (bad signature, schema mismatch, missing handle): returns a clear, distinct error

**P0.4 — Runnable in under 15 minutes**
- [ ] Single `README` with clone → install → seed → resolve steps
- [ ] No external network services required (index + facts served locally)
- [ ] One command seeds the index and signs all sample agents

### Nice-to-Have (P1)

**P1.1 — Capability-based discovery**
Query the index/facts for all agents matching a capability tag (e.g. `summarize-pdf`), returning matching handles. Demonstrates schema-validated capability assertions as a discovery primitive.

**P1.2 — Tamper-attack demo script**
A scripted path that flips a byte in a signed AgentFacts doc and runs the resolver, visibly producing a verification failure — the money shot for a live demo.

**P1.3 — Minimal web UI**
A single page: enter a handle, see resolved endpoint + capabilities, with a green "verified" / red "verification failed" badge.

### Future Considerations (P2)

- **TTL-scoped endpoints + revocation** — honor the TTL field, support key rotation, and show a previously-valid agent being rejected after revocation (the strong follow-on demo).
- **Registry Quilt federation** — multiple independent indexes with CRDT-merged, cross-signed deltas.
- **MCP/A2A bridge** — make a real MCP server discoverable through an index entry.
- **Privacy-preserving / least-disclosure queries** — return only the capability fields a consumer is authorized to see.

> Design note: keep AgentFacts as the single source of endpoint + capability truth (not the index) so P2 TTL/rotation work drops in without re-architecting.

## Success Metrics

This is a POC, so metrics are demonstration-quality and developer-experience oriented, not adoption numbers.

**Leading (evaluate at demo time)**
- **Resolution success**: 100% of the 5–10 seeded handles resolve to correct endpoint + capabilities.
- **Tamper rejection**: 100% of tampered/unsigned docs are rejected (zero false accepts).
- **Time to first resolve**: a new developer goes from clone to first successful resolution in < 15 minutes.
- **Demo clarity**: an audience member can articulate the handle → signed facts → verified endpoint loop after one walkthrough.

**Lagging (post-POC)**
- Decision-readiness: the POC is sufficient to greenlight (or decline) building the P2 TTL/revocation demo.
- Reusability: AgentFacts schema and resolver are reused by at least one follow-on POC without rewrite.

## Open Questions

- **[Engineering]** Where does the public key of record live — inline in the index entry, or referenced (e.g. a separate keyfile)? Inline is simpler for the POC; referenced is closer to NANDA. *(Blocking for P0.1/P0.3.)*
- **[Engineering]** Sign the canonical JSON-LD (with a canonicalization step) or sign a stable serialized blob? Canonicalization is more correct but adds complexity. *(Blocking for P0.2.)*
- **[Engineering]** CLI-only, or CLI + thin HTTP API for the resolver? Affects whether P1.3 web UI is feasible in the timebox. *(Non-blocking.)*
- **[Design/Demo]** What 5–10 sample agents tell the best story (e.g. a bank, a hospital, a PDF summarizer)? *(Non-blocking.)*
- **[Engineering]** Language/stack choice — Python (fast to write, good ed25519 + JSON-LD libs) vs Node (easier web UI). *(Non-blocking but decide early.)*

## Timeline Considerations

Suggested weekend phasing:

- **Phase 1 (P0.1–P0.2):** Define AgentFacts schema, write signing script, seed index with 5–10 signed agents.
- **Phase 2 (P0.3–P0.4):** Build the resolver with signature + schema verification; write the README; confirm the < 15-minute path.
- **Phase 3 (P1, if time):** Add capability discovery and the tamper-attack demo script; optional web UI.

No hard external deadlines. Main dependency is the early stack decision (open question above), which gates everything.