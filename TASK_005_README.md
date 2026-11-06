# KASPYRA Task 005 — Failure Thresholds and Architecture Decision

**Status:** local synthetic experiment; not a deployed network or satellite benchmark.

This task stress-tests the existing Task 004 transport model, holding the **aggregate number of transmission attempts per tick equal across strategies within each scenario**. It does not equalize the physical cost of maintaining a second network connection. Scenarios vary capacity, queue size, TTL, loss, outage duration, acknowledgment loss and propagation delay, one dimension at a time.

## Upload to GitHub

Upload only the following new files while preserving their relative paths:

- `experiments/failure_thresholds.py`
- `experiments/test_failure_thresholds.py`
- `docs/task005-results.json`
- `TASK_005_README.md`

**Dependency:** the existing `experiments/latency_ack_benchmark.py` from Task 004 must already be present. Do not overwrite Task 004 files. The experiment uses Python's standard library only.

## Reproduce

```bash
python -m unittest discover -s experiments -p 'test_*.py' -v
python experiments/failure_thresholds.py --trials 30 > docs/task005-results.json
```

Run from repository root. The first command runs all earlier tests as well if they are present. The new Task 005 test file contains 8 tests.

## Results (30 deterministic seeds per cell)

| Scenario | Single attempt | Retransmission | Dual-path |
| --- | ---: | ---: | ---: |
| Baseline | 49.0% | 100.0% | 100.0% |
| Capacity 1 attempt/tick | 29.5% | 48.2% | 65.6% |
| Queue 12 messages | 26.4% | 32.0% | 48.5% |
| TTL 12 ticks | 49.0% | 52.4% | 98.3% |
| Loss 70% | 17.3% | 71.6% | 84.6% |
| Primary outage 70 ticks | 19.7% | 24.5% | 100.0% |

The complete machine-readable outputs, including acknowledgments, overflow, expiry, duplicate receptions and attempts, are in `docs/task005-results.json`.

## Interpretation and limits

- **No L1 GO decision.** This model evaluates message transport, not validator consensus, inclusion, execution, finality, bridges or economics.
- **Dual-path optimism.** Backup is always usable during a primary outage; correlated/shared-fate failures are not implemented. A second path also has real-world cost.
- **Strategy equivalence.** Task 004's `retry` and `store_forward` share identical implementation behavior, so this task cannot demonstrate a distinction between them.
- **Synthetic conditions.** No Starlink or satellite traces, actual link capacity, modem behavior, weather, jitter, cost, or cryptographic authentication are measured.
- **No causal claims about a real satellite network.** Deterministic seeds are for reproducibility, not real-world statistical confidence.

## Decision gate for Task 006

Before a physical satellite pilot or custom chain decision, model **correlated failures and backup costs**, integrate a **real local blockchain node** and record transaction submission, inclusion and finality separately, and benchmark under measured/authorized network traces. A custom L1 requires a demonstrated security or utility advantage that a relay to existing chains cannot provide.
