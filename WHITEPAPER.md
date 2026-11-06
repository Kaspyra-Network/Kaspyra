# KASPYRA — Technical Whitepaper

**Research Draft 0.2 · 6 November 2026 · Not a deployed protocol specification**

## Abstract

KASPYRA investigates a narrow engineering problem: maintaining verifiable transaction submission and status visibility over intermittent communications. Its initial hypothesis is that authenticated, delay-tolerant forwarding can improve delivery under disruption while leaving transaction validity and settlement finality to a separate, independently secure consensus system. This hypothesis requires controlled testing and eventually authorized real-world measurements.

## 1. Problem and terminology

Terrestrial infrastructure can be disrupted by power failures, geographic isolation, disaster, censorship or equipment failure. Satellite connectivity may offer an additional route, but introduces cost, availability, latency, capacity, regulation and equipment dependencies. **Connectivity does not imply settlement.**

We distinguish: **signed** (user locally authorized a payload); **queued** (device or relay retains it); **submitted** (network endpoint accepted it); **included** (a block or ledger includes it); and **finalized** (the settlement system's defined finality condition is satisfied). An offline wallet can sign and queue, but cannot truthfully assert global finality while disconnected.

## 2. Design principles

- Transport independence: terrestrial, authorized satellite, or hybrid links.
- Cryptographic authentication and replay protection for relayed messages.
- Explicit acknowledgement and finality states, never fabricated confirmations.
- Safe behavior under partitions: prefer temporarily unavailable finality to contradictory settlement claims.
- Minimal trust in relays; end-to-end signatures and independently verified proofs.
- Evidence-based architecture selection; no assumption that a native token or new L1 is required.

## 3. Proposed architecture

**Wallet/application → authenticated store-and-forward queue → transport adapters → settlement gateway → independently verified chain or ledger.**

Transport adapters may use ordinary Internet access, a satellite Internet terminal, or another authorized carrier. Relays should support bounded queues, expiry, deduplication, retries with backoff, receipt verification, rate limits, and observability. Gateways must distinguish a transport-level acknowledgement from a ledger proof.

## 4. Competing designs

**A. Existing-chain transport overlay:** least consensus risk, fastest falsifiable prototype; inherits base-chain inclusion and finality constraints.

**B. Specialized existing-stack integration:** may permit better delayed submission or batching, but adds implementation and operational complexity.

**C. Dedicated L1:** offers more protocol control but requires a defensible consensus/security model, validator incentives, independent audits and demonstrable advantages. Not selected.

The initial experiment evaluates A's forwarding primitives before any choice of B or C.

## 5. Security and partition model

Assume hostile relays, compromised gateways, replayed payloads, withheld packets, clock drift, intermittent power, eclipsed peers and network partitions. Authentication does not guarantee delivery. Retries can create duplicates; deduplication must be idempotent and bounded. A majority partition may finalize according to a particular protocol while isolated users cannot independently verify current state. A system must not promise two conflicting finalized histories to disconnected domains.

A production design needs a precise consensus threat model, signing key lifecycle, fee/nonce handling, message expiry, proof verification, safe recovery and independent security review.

## 6. Satellite strategy

First test with local network impairment. Next compare terrestrial-only, satellite-only and hybrid **authorized ground-terminal** links using identical payloads and transparent measurement methodology. Satellite services can carry traffic; KASPYRA has no claimed access to software execution aboard satellites and no provider partnership.

## 7. Earth–Mars research direction

Earth–Mars communication delays and outages make a single synchronous global consensus domain impractical as a default assumption. A future study may examine independent local settlement domains exchanging asynchronously verified claims and receipts. Cross-domain transfers create bridge, escrow, replay, double-spend and recovery risks. No Earth–Mars payment implementation is claimed.

## 8. Hardware direction

An NFC-capable signing device with local transaction queueing, battery and possible solar-assisted charging is a possible later product. It should initially connect through existing authorized satellite equipment; direct handheld satellite integration is not assumed feasible.

## 9. Economics

A viable service must show real willingness to pay for reliable relaying, synchronization, verification or resilience. Compare infrastructure operating cost, bandwidth, maintenance and support against measurable customer demand. No token supply, presale, revenue projection or financing structure is approved by this draft.

## 10. Validation gates

1. Deterministic impairment simulations with explicit limitations.
2. Real-world transport measurements with consent and known equipment.
3. Threat-model and recovery review.
4. Demonstrated incremental benefit versus conventional retry and redundant terrestrial paths.
5. Commercial demand interviews and unit economics.
6. Only then revisit whether a custom chain is justified.

## 11. Research references

See [references](docs/references/README.md). These references are background sources, not validation of KASPYRA performance.

## Disclaimer

This is a research draft, not an investment offering, product availability claim, engineering certification, or affiliation with any satellite provider.
