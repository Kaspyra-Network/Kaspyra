# KASPYRA Task 013 — Phase B: validator P2P link experiment

This **additive** experiment starts four real local CometBFT v0.38.17 validators and the existing KASPYRA ABCI application. It adapts the repository's proven Task 009B P2P proxy harness.

## What is measured

- All four validators converge before impairments.
- Actual CometBFT P2P TCP bytes are forwarded through 12 directed localhost proxies.
- Proxy forwarding adds 100 ms and then 300 ms **per received TCP chunk**. This is *not* a calibrated RTT emulator: application-level timing and TCP backpressure will change the effective delay.
- Three further blocks are committed at each delay level; elapsed time, forwarded bytes, chunk counts and heights are recorded.
- A verified 2-versus-2 partition stops block progress for a 12-second observation period, then reconnects and converges again.

## Boundaries

This does **not** integrate Task 012's signed store-and-forward envelope into CometBFT P2P. Its envelope is for transaction delivery, not a safe replacement for CometBFT's authenticated persistent peer transport. This does **not** test actual satellites, GNSS, DTN, jitter, loss, RF, or end-to-end terrestrial independence. It does not validate production security or viability under long satellite disruptions.

## Run

Use the included GitHub Actions workflow, or install Go 1.23, CometBFT 0.38.17 and Python 3.11, then run `python task013b/run_validator_link_experiment.py` from the repository root. The report is `task013b-result.json`. No production keys or funds are involved.

## Interpretation

PASS means local CometBFT liveness under these particular controlled impairments and safe halt/recovery on a 2/2 partition. It is **not** a satellite-only GO decision. Next: calibrated `tc netem`/WAN or real satellite measurements with loss/jitter/RTT, then provider path verification.
