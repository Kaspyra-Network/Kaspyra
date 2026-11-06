# KASPYRA — Task 003: Constrained Network Simulation

**Status:** Deterministic synthetic experiment; not satellite telemetry, blockchain consensus, or a deployed service. November 6, 2026.

## Installation / publishing

This package is **additive** to Tasks 001 and 002. Upload the extracted `experiments/` and `docs/` directories to the root of `Kaspyra-Network/Kaspyra`, preserving paths, and place `TASK_003_README.md` at the root. **Do not delete or overwrite** existing Task 001/002 files or GitHub Actions workflows. Existing CI using `python -m unittest discover -s experiments -p 'test_*.py' -v` will discover these new tests.

## Run locally

```sh
python3 experiments/constrained_network.py --benchmark
python3 -m unittest discover -s experiments -p 'test_*.py' -v
```

The `docs/task003-results.json` file records the deterministic six-case benchmark. No third-party dependencies, satellite terminals, RPC endpoints, credentials, or payments are required.

## Model

Each tick, messages enter a finite queue. They have an ID, creation time, TTL and a synthetic priority (one in four marked critical). The model expires queued messages, admits arrivals up to queue capacity, then transmits a bounded number of messages per active link. Failed attempts are requeued and consume link capacity. Two scheduling strategies are FIFO and priority-first. Primary and optional backup paths may be simultaneously unavailable (correlated outage) or independently available. A SHA-256-derived deterministic draw models transmission loss. Results include delivered, overflow, expired, pending, peak backlog, attempt counts, recovery backlog, delivery delay, and priority breakdown.

**Important limitations:** A message occupies one capacity unit irrespective of size; there is no byte-level bandwidth, serialization delay, propagation latency, acknowledgment, custody transfer, authenticated deduplication, economic cost, fairness guarantee, Byzantine node, satellite orbital visibility, validator quorum or finality model. The optional backup adds capacity rather than holding total capacity constant. A failed send is retried within the same bounded queue; there is no end-to-end ACK simulation. Priority scheduling may starve ordinary traffic under sustained load. `ttl` is an arbitrary tick count, not a blockchain transaction's actual validity window. These results cannot establish safety or live reliability.

## Fixed benchmark settings

60 ticks; messages arrive at 6 per tick for the first 25 ticks (150 total); primary link capacity 5 attempts/tick; backup capacity 3 attempts/tick when enabled; primary outage ticks [10,22); loss 5%; queue capacity 60; TTL 30 ticks unless varied; seed 42. Backup outages are either correlated with the primary or independent. See `parameters` in the JSON for exact settings.

| Case | Delivered / 150 | Overflow | Expired | Peak queue |
|---|---:|---:|---:|---:|
| Primary FIFO | 116 | 34 | 0 | 60 |
| Primary priority | 117 | 33 | 0 | 60 |
| Independent backup | 150 | 0 | 0 | 44 |
| Correlated backup | 132 | 18 | 0 | 60 |
| Tight queue (15) | 71 | 79 | 0 | 15 |
| Short TTL (8 ticks) | 89 | 0 | 61 | 48 |

## Interpretation and decision gate

- Finite queues produce loss under sustained overload or outages.
- Expiry creates a fundamental tradeoff between stale delivery and eventual delivery.
- An actually independent backup path can improve availability in this model; a shared outage undermines that benefit.
- Adding a backup link adds bandwidth. **Do not** interpret its performance as proof that redundancy is more efficient at equal cost or equal aggregate bandwidth.
- The priority result is marginal and should not be used to justify a priority policy without starvation and fairness analysis.

**Next gate:** benchmark equal total link capacity and realistic byte-size distributions; add explicit propagation latency, end-to-end ACKs, link-cost accounting, and real trace replay. Only then evaluate satellite connectivity under authorized field measurements. No dedicated L1 decision, token, or hardware purchase is justified by Task 003.
