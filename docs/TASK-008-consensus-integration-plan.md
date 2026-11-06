# Task 008 consensus integration gate

**Research direction:** CometBFT's ABCI++ separates BFT block ordering/finality from the application's deterministic transaction execution. KASPYRA remains a sovereign L1 if it owns its genesis, validators, state machine and currency; it does not need to invent a new consensus algorithm.

**Do not confuse:** four Go ledger replicas with four CometBFT validators. Phase A provides only the former's deterministic execution foundation, not even networked replicas.

**ABCI correctness gates:** CheckTx is admission filtering, not authoritative block execution. ProcessProposal must reject invalid proposals deterministically. FinalizeBlock applies block transactions in canonical order and returns per-transaction results and state commitment. Commit must atomically persist the finalized state, and Info must report the exact committed height and hash for replay/crash recovery. Never persist speculative state as committed state. Proposal validation must account for sequential nonces and cumulative balances within the block. Validators need identical genesis allocations and transaction byte formats.

**Safety and liveness:** BFT quorum requires >2/3 voting power. If connectivity falls below quorum, finality halts. Store-and-forward and satellite transports may improve eventual delivery but cannot override consensus quorum. No claim of safe Earth-Mars synchronous finality.

**Acceptance evidence required:** exact CometBFT version; four-node reproducible start commands; signed transfer transaction hash; matching finalized block heights and app hashes across four nodes; validator restart; deliberate quorum loss and recovery; crash-replay checks; passing CI logs. None of these are yet demonstrated by this package.

Sources: https://github.com/cometbft/cometbft/blob/main/spec/abci/abci%2B%2B_app_requirements.md ; https://pkg.go.dev/github.com/cometbft/cometbft/abci/example/kvstore
