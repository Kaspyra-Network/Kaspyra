# Research questions and evidence ledger

## Open questions

1. Does store-and-forward outperform ordinary retry under equivalent network and storage budgets?
2. What are the costs and failure modes of terrestrial/satellite failover?
3. Which chains expose independently verifiable inclusion and finality proofs suitable for delayed links?
4. What nonce, fee and expiry behavior is safe for queued offline transactions?
5. What happens when the user is partitioned from the current consensus majority?
6. Can relays remain untrusted without compromising usability?
7. When, if ever, does a purpose-built L1 outperform a transport overlay enough to justify new consensus risk?
8. Is there demonstrated customer demand for this resilience?
9. Can asynchronous settlement domains be composed without an unsafe bridge trust assumption?

## Evidence rules

Every reported benchmark should include code version, seed, parameters, trial count, hardware/network conditions, baseline, uncertainty and limitations. Label observations separately from assumptions and marketing aspirations. Never call a synthetic scenario a measured Starlink result.

## Initial claims register

| Claim | Status |
|---|---|
| A local simulator can model synthetic packet loss and partitions | Implemented in this repository; verify by running tests |
| KASPYRA improves real satellite connectivity | **Unverified** |
| KASPYRA has deployed a validator network | **False / not deployed** |
| Earth–Mars settlement is implemented | **False / research aspiration** |
| KASPYRA has a Starlink/SpaceX partnership | **No such partnership claimed** |
