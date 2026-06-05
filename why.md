# Why This Matters: NANDA Agent Resolver POC

**Companion to:** NANDA Agent "Business Card" Resolver PRD
**Last updated:** May 23, 2026

---

## The Problem in One Line

AI agents are multiplying fast, but there is no open, vendor-neutral way to *find* an agent and *trust* it's the real one — and the whole agentic web breaks down without that.

## Why This Matters

### The web is heading toward billions of agents with no address book
We already have an early "app store" model emerging — agents published inside single commercial platforms. But that recreates the walled-garden problem: discovery, identity, and trust all controlled by one vendor. The open web solved this for websites decades ago with DNS + TLS certificates. The agentic web has no equivalent yet. NANDA's bet is that agents need their own "DNS + verifiable identity" layer, and this POC builds the smallest honest version of it.

### A raw endpoint URL carries zero trust
Today, if an agent says "I'm `acme-billing-bot`, call me at this URL," there's nothing stopping anyone from impersonating it, lying about its capabilities, or silently swapping the endpoint. For agents that move money, touch health records, or act autonomously, that's a serious gap. Cryptographic signing of AgentFacts means a consumer can verify provenance *before* connecting — a zero-trust posture by default.

### Discovery and capability advertising are unsolved at scale
When one agent needs another ("find me something that can summarize a PDF and is compliance-tagged"), there's no standard, machine-readable way to ask. Schema-validated capability assertions turn discovery into a query instead of a phone call or hard-coded integration.

### It's the right wedge into a much bigger architecture
NANDA's full vision — the Registry Quilt, federation, TTL-scoped revocation, MCP/A2A bridging — is large and abstract. The resolver is the *load-bearing primitive* underneath all of it. If the handle → signed facts → verified endpoint loop works, everything else is an extension. If it doesn't, none of the rest matters. Proving this first is the highest-leverage thing to build.

## Why I Chose This (out of the five options)

I evaluated five candidate POCs (resolver, capability discovery, sub-second revocation, MCP/A2A bridge, mini Registry Quilt). I chose the resolver for four reasons:

1. **Highest concept-to-effort ratio.** It demonstrates the *entire* NANDA thesis — discovery + identity + verifiable capabilities — in something buildable in a weekend. The other options are either narrower (revocation alone) or far heavier (the Quilt needs CRDTs, gossip, multi-registry sync).

2. **It's the foundation everything else sits on.** Capability discovery, revocation, and federation all assume a working resolve-and-verify loop. Building the foundation first means the follow-on POCs become extensions, not rewrites. The PRD deliberately keeps AgentFacts as the single source of endpoint truth so the P2 work drops in cleanly.

3. **It produces a clean, undeniable demo.** "Here's a handle. Here's the verified endpoint and capabilities. Now watch me tamper with the document — and watch the resolver reject it." That arc is legible to both engineers and non-technical stakeholders in one sitting.

4. **It's faithful to the real architecture, not a toy.** It uses the actual NANDA primitives — a lean index, Ed25519-signed JSON-LD AgentFacts, schema validation — rather than a hand-wavy mock. That means the learnings transfer directly to the bigger build.

**What I consciously traded away:** live endpoint rotation and sub-second revocation (the flashiest single feature) and federation (the most impressive technically). Both are deferred to P2 because neither is meaningful without the resolve-and-verify loop existing first. Scoping down here is the point, not a limitation.

## Expected Outcomes

### What we'll have at the end of the weekend
- A runnable lean index of 5–10 agents under readable handles.
- Ed25519-signed, schema-validated AgentFacts documents for each.
- A resolver that turns a handle into a *verified* endpoint + capability list, and rejects anything tampered or unsigned.
- A reproducible setup any developer can run in under 15 minutes.
- (If time allows) capability-based discovery and a live tamper-attack demo.

### What we'll learn (the real point of a POC)
- **Is the trust model sound?** Does signing/verifying AgentFacts actually catch tampering and impersonation cleanly, with clear failure modes?
- **Where's the friction?** The open questions in the PRD — key storage, JSON-LD canonicalization, signing strategy — get answered by building, not arguing.
- **Does the minimal-index principle hold?** Can we really keep the index lean and push all endpoint/capability detail into AgentFacts without it getting awkward?
- **Is the demo persuasive?** Does the resolve-then-tamper arc land with an audience well enough to justify investing in the bigger architecture?

### What this unlocks next
A working resolver is the green light (or the informed "not yet") for the higher-ambition POCs:
- **Sub-second revocation + TTL rotation** — the strongest standalone demo, now trivial to add on top.
- **Capability marketplace / discovery** — querying the agent ecosystem by what agents *do*.
- **MCP/A2A bridge** — making real existing agents discoverable through the index.
- **Registry Quilt** — federating multiple independent registries into one fabric.

### How we'll know it worked
- 100% of seeded handles resolve correctly; 100% of tampered docs rejected (zero false accepts).
- A new developer reaches first successful resolution in under 15 minutes.
- An audience member can explain the handle → signed facts → verified endpoint loop after one walkthrough.
- We can make a confident, evidence-based decision about building the next POC — instead of guessing.

## The One-Sentence Pitch

If the agentic web is going to be open rather than owned by a handful of platforms, agents need a DNS-and-certificates layer of their own — and this POC proves the smallest piece of that is real, runnable, and trustworthy.