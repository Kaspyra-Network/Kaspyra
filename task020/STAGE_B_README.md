# Task 020 Stage B — asymmetric connectivity

Separate CI-only four-validator CometBFT test. Keeps Stage A unchanged.

- Rotate a fully isolated minority between validator 3 and validator 0; require the connected 3-validator quorum to advance while the minority remains stalled.
- Block routes only in one direction from validators 0–2 toward validator 3; record resulting heights without assuming a TCP connection can work unidirectionally.
- Require matching majority block/application hashes and convergence of all four nodes after each recovery.
- Record blocked routes and failed new TCP connection attempts. Established TCP payload isolation is **not** independently packet-captured.

No real satellite transport or formal safety proof. Execute only on a disposable GitHub-hosted runner, **never** on the production VPS. Evidence: `task020-asymmetric-evidence.json`.
