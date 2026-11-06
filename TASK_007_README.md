# KASPYRA Task 007 — Local execution prototype and consensus stack decision

**Status: prototype only. No consensus or finality implementation.**

This incremental package preserves Tasks 001–006. It adds:
- `experiments/kaspyra_local_chain.py`: Ed25519 signed native transfers, chain-ID binding, nonce/replay checks, balance checks, deterministic state hashes, and four isolated Python worker processes.
- `experiments/test_kaspyra_local_chain.py`: 13 focused tests, including multi-process execution.
- `docs/ADR-0004-consensus-stack-selection.md`: CometBFT/Cosmos SDK comparison and next validation gate.

## Setup and run

Requires Python 3.11+ and `cryptography` (version range in `requirements-task007.txt`).

```bash
python -m pip install -r requirements-task007.txt
python -m unittest discover -s experiments -p 'test_*.py' -v
python experiments/kaspyra_local_chain.py
```

## CI

Existing GitHub Actions job must install dependencies **before** unittest discovery. Merge the following step after `actions/setup-python` and before the test step:

```yaml
- run: python -m pip install -r requirements-task007.txt
```

Alternatively replace `.github/workflows/tests.yml` with the included updated workflow **only if** the existing workflow still matches the simple Python-only workflow from Task 001. Inspect your existing workflow before replacing it.

## Important limits

The four workers do **not** communicate with each other. A trusted coordinator supplies identical transactions. This is not a blockchain consensus network, Byzantine fault tolerance, partition recovery, cryptographic finality, durable disk state, or production-grade account encoding. It cannot safely hold real value. The first actual multi-validator BFT network belongs to Task 008.
