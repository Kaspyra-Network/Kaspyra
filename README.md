# Task 013 — Authenticated transport to finalized KASPYRA transaction

This integration extends the **real four-validator local CometBFT experiment** from Task 010 and uses the **Task 012** signed, SQLite-backed transport. It tests: offline sender queue, reconnection, receiver authentication and duplicate suppression, RPC submission of the persisted transaction, four-validator finality/state agreement, expiry rejection and restart persistence.

## Boundaries

- Local TCP transport, **not** a physical satellite link or a validator-to-validator satellite connection.
- Consensus P2P and ABCI++ remain unchanged. Task 012 delivery acknowledgment **does not imply chain finality**; Task 013 explicitly waits for transaction inclusion and state convergence.
- Gateway submission is a test-harness operation, **not** a production transaction processor. The inbox lacks a production-grade exactly-once RPC submission state machine, and the transport is not production hardened.
- This patch is additive. No changes to existing ledger/consensus source files.

## CI

Upload the contents of the implementation ZIP to repository root and upload the workflow YAML separately to `.github/workflows/task013-transport-chain.yml`. Run **KASPYRA Task 013 Transport to Chain** in GitHub Actions. It builds CometBFT v0.38.17, compiles the existing ABCI application and runs the end-to-end four-validator integration.

## Success evidence

Expected markers: `TRANSPORT_OUTAGE_QUEUE PASS`, `SIGNED_TRANSPORT_DELIVERY PASS`, `TRANSPORT_TO_FINALITY PASS`, `EXPIRED_ENVELOPE_REJECTED PASS`, `PERSISTENT_RESTART_STATE PASS`. The `task013-result.json` artifact includes the transaction hash and finality evidence.

## Limitations

Do not claim a satellite-only blockchain based on these tests. The next step is verified satellite-provider routing and physical link testing, followed by separate validator P2P transport feasibility.
