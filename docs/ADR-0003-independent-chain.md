# ADR-0003 — Independent KASPYRA chain as product direction

**Status:** Research direction selected; technical stack undecided. 2026-11-06.

## Context

KASPYRA's intended product is a new independent blockchain with native settlement, validator infrastructure, and disruption-tolerant networking. Earlier Research 001 favored evaluating a transport overlay first as a lower-risk experiment. This ADR **supersedes that product preference** without invalidating its experimental evidence or authorizing a custom consensus implementation.

## Decision

Research and prototype an independent KASPYRA blockchain. Use existing battle-tested consensus and execution components where feasible; **independent chain does not require inventing a new consensus algorithm**. Evaluate candidate stacks against explicit requirements: deterministic finality, validator recovery, upgrade safety, resource requirements, permissionless participation roadmap, satellite-aware networking, wallet compatibility and interoperability.

- The base chain is independent; BTC, ETH and SOL are **external funding currencies** initially, not native chain assets or automatic bridge deposits.
- Native token supply, validator economics, staking and issuance remain **unapproved hypotheses**.
- The proposed founding funding program is a **separate future-token sale design**, not staking or a redeemable deposit. No live contribution collection is authorized.
- Earth–Mars settlement is long-term research involving separate local finality domains and asynchronous verified messages; it is not a single synchronous consensus network.

## Alternatives retained for evaluation

1. Modular independent chain with established BFT consensus and deterministic execution.
2. Independent rollup / appchain with external security dependencies (not equivalent to sovereign L1).
3. Bespoke consensus: reject unless existing solutions demonstrably fail requirements and independent expert review justifies added attack surface.

## Decision gates

1. Written consensus fault assumptions, quorum rules and explicit finality semantics.
2. Working local multi-validator testnet with reproducible partitions and restart recovery.
3. Signed transactions, deterministic state transitions, chain identity and replay protection.
4. Security threat model and independent review plan.
5. Economic model showing credible long-term validator participation under adverse conditions.
6. Separate BTC/ETH/SOL funding, custody and future interoperability specifications with explicit failure treatment.

No claim of validated production security is justified by quorum arithmetic or transport simulation alone.
