# ADR-0004 — Independent chain stack selection (research, not adopted)

## Decision candidate

Prefer evaluating **Cosmos SDK + CometBFT** as the initial sovereign KASPYRA L1 implementation stack. The alternative is a custom consensus implementation, which introduces substantial unnecessary safety and audit risk. A third candidate is a minimal custom application state machine connected to CometBFT via ABCI, to reduce SDK integration complexity for early prototypes.

## Why this is not yet a final selection

A working prototype with real CometBFT processes, version-pinned dependencies, reproducible builds, tested validator restarts, proposer changes, byzantine fault assumptions, and partition recovery is required. Licensing, operational complexity, performance and satellite-delay tolerance must be evaluated. CometBFT's partial-synchrony assumptions and quorum requirements mean that a severe partition can halt finality. Store-and-forward transport cannot override that safety constraint.

## Explicit scope boundary

Task 007 provides a **Python deterministic execution demonstration** with four independent worker processes and signed transfers. The demo sends the same transaction to each process from a trusted coordinator. **It has no validator votes, network gossip, leader election, consensus, adversarial behavior, or finality**. Matching state hashes are not a proof of consensus. Do not use it for custody or public funds.

## Next gate

Task 008 should integrate a version-pinned CometBFT/ABCI application in an isolated development environment and demonstrate actual validator consensus with fault/restart tests. Keep funding contributions, staking, bridges and mainnet out of scope.
