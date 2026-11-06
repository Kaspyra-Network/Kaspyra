# KASPYRA Task 009B — real P2P partition and ABCI recovery

Experimental local-only CometBFT v0.38.17 harness. **Not yet CI-verified** at package creation.

## Upload

Extract this ZIP into the root of `Kaspyra-Network/Kaspyra` while preserving paths. It adds `task009b/run_partition_recovery.py`, `.github/workflows/task009b-network.yml`, and this README. It does not replace Task 008D or 009A.

## Experiments

- Four CometBFT validator and ABCI processes are launched with 12 dedicated directed TCP forwarding links. Peer exchange (`pex`) is disabled. Each validator's configured persistent peer routes use its link-specific proxy; proxies are part of the test harness, not the blockchain.
- Partition `{0,1}` from `{2,3}` by closing and refusing every cross-group TCP link. All eight processes remain running. Verify each validator sees its within-group peer but no opposite-group peers, then verify no new block heights across a 15-second observation window after a four-second drain.
- Restore the links and verify all four validators progress and agree on block ID and application hash at the same height.
- Stop validator 1's consensus process and ABCI process, preserve committed state, restart ABCI then consensus, verify catch-up and persisted balances/nonces.

## Limitations and safeguards

- The isolation uses **user-space TCP proxies**, not OS firewall namespaces. It is valid only if all CometBFT P2P traffic passes through the configured proxies. `pex=false` and explicit peer identity checks help detect bypass; a future network-namespace experiment would provide stronger independent isolation.
- This phase tests process recovery with unchanged development fixture balances. **It does not submit a new signed transfer after restart**. That remains a separate acceptance criterion for the full Task 009 and must not be represented as passed.
- The test is fail-closed on missing peer isolation, process exit, unexpected block advancement, mismatched hashes, or persisted-state inconsistency.
- No Byzantine safety proof, production deployment, or satellite-link validation is claimed.
- GitHub Actions may reveal version/configuration or proxy edge cases. Share the failed job log for correction; do not mark the task complete until the dedicated workflow reports `PASS_PHASE_B`.
