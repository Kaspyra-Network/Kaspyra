# KASPYRA Task 008 — Phase A: Go ledger foundation

**Status: Go ledger locally tested. CometBFT integration NOT implemented.**

This package establishes a small native Go deterministic transaction engine with Ed25519 signing, domain-separated chain ID, nonce/replay rejection, overspend checks, and deterministic state hashing. It is a stepping stone toward an ABCI++ application. It does not operate validator nodes, vote, finalize blocks, or implement networking.

## Why staged?

The build environment cannot reach proxy.golang.org to retrieve CometBFT dependencies, and Docker is not available. A claimed fully verified four-validator network would be misleading. The CometBFT ABCI++ integration must be implemented and tested in an environment with dependency access and containers before it can be accepted.

## Upload

Extract and upload the `task008/`, `docs/`, `.github/` paths to the repository root. Do **not** overwrite the existing `.github/workflows/tests.yml`. The new `task008-go.yml` workflow runs independently of the earlier Python research suite. Commit `feat: add Task 008 Go ledger foundation`.

## Local commands

```sh
cd task008
go test -race -count=1 ./...
go run .
```

Go 1.23.2 or newer is recommended for this dependency-free package.

## Next implementation gate: Phase B — actual CometBFT

1. Pin a supported CometBFT release and review its exact ABCI++ API.
2. Implement Info, InitChain, CheckTx, PrepareProposal, ProcessProposal, FinalizeBlock, Commit and Query with durable state and crash recovery.
3. Define deterministic genesis allocations, chain ID, transaction encoding and error codes; reconcile Task 007's Python signing format before any migration.
4. Run four independent CometBFT processes with distinct keys, P2P links and separate ABCI app instances.
5. Submit a signed transfer over RPC, verify 4 matching app hashes, stop/restart one validator, then test quorum loss and restoration.
6. Add end-to-end CI only once the real processes run reproducibly. Never label the Go ledger demo as decentralized finality.

## Known limitations

- No persistence, consensus, fee charging, validator economics, ABCI, snapshotting, state proofs or security audit.
- Hash is deterministic serialization + SHA-256, not a Merkle commitment.
- Signing JSON is intentionally an experimental new format and is not byte-compatible with Task 007.
- This prototype must not custody or process public funds.
