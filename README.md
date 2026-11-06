# KASPYRA Task 008D — four-validator integration candidate

This package adds a **real CometBFT process integration smoke test** to the existing `task008c/` application. It does not replace the existing code. Upload `task008d/` and `.github/workflows/task008d-network.yml` to the repository root.

## What the runner attempts

- Build the existing `task008c` ABCI application.
- Generate four separate CometBFT validator identities and data directories with the **same genesis** and four validators.
- Start four ABCI servers and four independent CometBFT processes on distinct loopback ports.
- Generate ephemeral Ed25519 account keys, sign a transfer of 125 test units, and broadcast it through CometBFT RPC.
- Check transaction inclusion, matching application hashes at the same height, all four persisted account balances, and restart of one consensus node.

## Verification status

**UNVERIFIED against a live CometBFT network in the packaging environment.** The environment cannot retrieve the CometBFT Go module or binary. The GitHub Actions integration workflow is the first actual run and may uncover API/configuration incompatibilities. A passing test would demonstrate a local integration smoke test, **not** Byzantine security, network partition safety, or production readiness. Do not announce a working validator network before this job succeeds and logs are reviewed.

## Upload and run

1. Upload `task008d/run_four_validators.py` and `.github/workflows/task008d-network.yml` preserving paths.
2. Commit `test: add Task 008D four-validator integration harness`.
3. Check the **KASPYRA Task 008D Four Validator Integration** workflow.
4. If red, share the failing step and final error lines; preserve logs and correct the precise issue.

This uses test-only ephemeral keys and local ports. It does not accept funds, expose public RPC, or deploy a mainnet.
