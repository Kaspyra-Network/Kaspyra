# KASPYRA Task 008C — experimental CometBFT ABCI++ adapter

**Status: source implementation supplied; NOT validated against CometBFT or a four-validator network.**

This package contains a Go ABCI++ socket application built around the existing Task 008 ledger logic, with CheckTx, PrepareProposal, ProcessProposal, FinalizeBlock, Commit, Info, and disk state persistence. It pins CometBFT v0.38.17 as a candidate dependency. Network access to Go module servers is unavailable in the package-building environment; **the Go adapter has not been compiled or executed here**. CI must determine whether the pinned API compiles, and failures require fixing before any validator test.

## GitHub upload

Upload `task008c/` and `.github/workflows/task008c-abci.yml` to repository root. Preserve previous task folders and workflows. Commit `feat: add experimental CometBFT ABCI adapter`.

## CI acceptance gates

1. GitHub Actions `KASPYRA Task 008C ABCI` downloads dependencies and compiles/tests successfully.
2. Run four real CometBFT nodes with unique validator keys and four independent ABCI instances, matching chain ID and balances; capture their RPC status, block hashes, and app hashes.
3. Broadcast a signed transfer and demonstrate four identical finalized app hashes.
4. Restart a node, lose quorum, restore quorum, and prove consistent state without conflicting finalized blocks.

**Do not mark Task 008C complete until all four gates pass.** This package does NOT include a verified four-validator harness. It is an integration candidate, not production code or a verified blockchain. No real funds.

## Known issues to address before real validator trials

- ABCI API and CometBFT version compatibility must be confirmed by CI.
- Proposal filtering, consensus-vote handling, InitChain and Query need complete protocol treatment.
- Crash recovery between FinalizeBlock and Commit needs rigorous replay testing.
- Disk persistence needs directory fsync, lock handling and corruption recovery.
- Transaction pool admission must account for multiple pending transactions from the same sender.
- Genesis balance file must be identical and validated on every node.
- Hash uses ASCII hex bytes and is not a Merkle commitment.
- No fees, staking, validator economics, snapshots, light-client proofs, bridge, or satellite transport.
