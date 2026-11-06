# KASPYRA Task 006 — Independent chain architecture research

**Status: research / educational model; no functioning chain.**

This milestone documents the product decision to research an **independent KASPYRA blockchain**, rather than make an existing-chain relay the end product. Previous transport experiments remain relevant as supporting networking research. This is not proof that a new L1 is more secure, efficient, or commercially viable.

## Included

- `docs/ADR-0003-independent-chain.md` — architecture direction and decision gates.
- `docs/task006-consensus-research.md` — finality, partition, validator, interoperability and fundraising boundaries.
- `experiments/partition_finality.py` — deterministic **static quorum arithmetic**, not a consensus implementation.
- `experiments/test_partition_finality.py` — 12 tests.

## Reproduce

From repository root:

```bash
python -m unittest discover -s experiments -p 'test_*.py' -v
python experiments/partition_finality.py
```

The model illustrates that in a 7-validator fixed membership set with a >2/3 quorum, a 5/2 split leaves one quorum-capable partition, while a 4/3 split leaves none. **It does not prove Byzantine safety, liveness, signatures, correct leader changes, state-machine replication, or secure finality.**

## Next evidence gate

Build a **local-only, multi-process prototype** using an established audited consensus library or implementation, not a bespoke consensus algorithm. Test signed transactions, deterministic execution, adversarial partitions, leader changes, validator restarts, state sync and finalized receipts. Do not deploy a token, solicit funding, or accept BTC/ETH/SOL until separately authorized and operationally ready.
