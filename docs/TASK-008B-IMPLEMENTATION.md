# KASPYRA Task 008 Phase B — consensus integration contract

Status: **implementation plan and verification harness; integration NOT yet demonstrated**.

## Goal
Integrate the existing `task008` deterministic ledger with a pinned, production-maintained CometBFT release through ABCI++. Preserve all earlier research and CI. KASPYRA is an independent L1, not an existing-chain relay.

## Implementation sequence
1. Choose and pin a specific CometBFT release and Go toolchain, recording its official API docs and checksum. Avoid `main` or unbounded version ranges. Verify actual ABCI++ method signatures against the pinned release.
2. Refactor `task008` ledger into an importable package **without breaking** its current demo and tests; do not change the signed transaction payload format silently.
3. Implement ABCI++ `Info`, `InitChain`, `CheckTx`, `PrepareProposal`, `ProcessProposal`, `FinalizeBlock`, `Commit`, and relevant snapshot/vote-extension behavior using the pinned version's exact interface.
4. `CheckTx` is advisory only. `ProcessProposal` simulates **the full proposed block** on a clone and rejects invalid transactions, including sequential nonce and cumulative balance errors. `FinalizeBlock` executes deterministically, returning ordered transaction results and app hash. Do not confuse execution with finality.
5. Store **committed** height, app hash, and state atomically on disk; persist genesis fingerprint. Crash/restart must never report speculative state as committed. Handle CometBFT replay semantics and verify `Info` against committed state. No hardcoded private keys.
6. Supply four distinct CometBFT node homes, validator identities, shared genesis, per-node application state, peer configuration and documented start/stop scripts. Ensure all nodes independently run the application and reach consensus without a coordinator forging results.
7. Supply reproducible signed transfer submission, chain-ID separation, transaction hash lookup, height/app-hash checks across four nodes, restart, quorum-loss and restoration tests. Ensure failure tests use isolated localhost nodes, no public networks.
8. Gate CI: unit tests always run; integration tests run in a separate job with downloaded pinned binaries, checksums, bounded timeouts, log capture and cleanup. Never mark integration green if skipped.

## Critical acceptance checks
- Four **real** CometBFT validator processes plus four ABCI application processes.
- One valid signed transfer appears in finalized blocks; balances, nonces and app hashes match on all four nodes.
- Invalid signatures, cross-chain replay, insufficient funds, nonce replay, and multi-tx block double spend are rejected consistently.
- Restart one validator/app: it catches up and reports identical committed state.
- Stop two of four equal-power validators: no new finalized blocks. Restore them: finalization resumes with no conflicting history.
- Kill application around commit boundary; recovery/replay does not double-apply a transfer.
- Include exact command output, CometBFT version, CI run URL, heights, hashes and observed limitations in the evidence report.

## Security caveats
CometBFT provides consensus ordering/finality only under its specified assumptions. KASPYRA's application, persistence, key management, genesis, and networking require independent review. A local demonstration is not a production-ready chain. Satellite links, BTC/ETH/SOL bridges, staking and fundraising contracts are explicitly out of scope.

## Recommended developer command
Use this document as the implementation brief for Codex or a Go developer with network access. Do not merge or announce Phase B as completed until the acceptance checks above are independently reproducible.
