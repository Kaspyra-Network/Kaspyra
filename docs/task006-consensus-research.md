# Task 006 — Consensus and interoperability research notes

## Safety versus liveness

A validator network may deliberately **stop finalizing** during a severe partition. The network must not claim that offline signing, queue acceptance, transport acknowledgement, block inclusion and finalized settlement are the same state. For a fixed validator set, quorums must intersect; a quorum threshold alone does not establish a secure BFT protocol. Real safety depends on signed voting rules, locking, membership transitions, evidence handling, authenticated transport, state-machine determinism and Byzantine fault assumptions.

## Illustrative quorum model

For `n` fixed validators, the educational model uses `q = floor(2n/3) + 1`. For `n = 7`, `q = 5`. Under a 4/3 split, neither partition has five reachable members; under a 5/2 split, one does. This does **not** model network delays, voting rounds, faulty equivocation, dynamic membership, proposer selection or consensus safety.

## Transport versus settlement

Transaction stages: `SIGNED -> QUEUED -> SENT -> RECEIVED -> VALIDATED -> INCLUDED -> FINALIZED`. A relay's receipt is not finality. Queues require bounded storage, TTL, canonical message IDs, deduplication, encrypted local storage, and explicit rejection handling.

## External assets and initial funding

The project may eventually offer verified BTC, ETH and SOL interoperability, but the initial funding concept is a future-token allocation in exchange for development contributions. Contributors must know whether their assets are **spent as development funds** and that they are **not redeemable deposits or staking positions**. Any future bridge must have separate reserve, custody, redemption and proof rules. Never conflate sale proceeds with backing collateral.

## Research backlog

- Compare mature consensus implementations by safety assumptions, operational complexity, finality under partitions, validator rotation and implementation maturity.
- Test local validators under delayed, lost, reordered and duplicated messages with fixed equal network resources.
- Specify fee market, account model, transaction signature scheme, chain ID, validator governance, slashing and upgrade path.
- Independently model fixed-supply validator security reserve against an inflationary alternative; do not assume fees cover validator costs.
- Model BTC/ETH/SOL contribution FX pricing, custody risk, delivery failure, vesting and transparent treasury reporting separately from bridge design.

## Evidence boundaries

Current Tasks 001–005 are synthetic transport research. Task 006 adds only a **mathematical teaching model**. There is no implemented KASPYRA chain, satellite network, token, wallet bridge or staking product.
