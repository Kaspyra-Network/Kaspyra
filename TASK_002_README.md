# KASPYRA — Task 002: Synthetic Transport Comparison

**Status:** Local synthetic research experiment, not deployed infrastructure. 2026-11-06.

This is an **additive update** to the Task 001 repository. It does not replace the existing README, license, or experiment. Copy the `experiments/` and `docs/` directories into the repository root, retaining their paths.

## Purpose

Compare four *message-transport policies*, not blockchain implementations:

- `single_attempt`: send once on primary path at tick 0.
- `bounded_retry`: attempt on primary at ticks 0, 3, 6, 9.
- `store_forward`: queue and retry on primary every 3 ticks through the observation window.
- `dual_path`: queue and send on primary and independent backup paths every 3 ticks.

Scenarios are synthetic: nominal conditions, lossy primary path, temporary shared partition, primary-only outage, and complete partition. Each policy uses identical deterministic path/time random draws per message. The receiver counts each message ID once and records excess arrivals as suppressed duplicates. **Authentication, bandwidth, costs, propagation, backpressure, node clocks, Byzantine actors, validator quorum, chain reorganization, consensus safety and finality are not modeled.** The model also continues scheduled attempts after first delivery to measure potential duplicate arrivals; attempt counts therefore represent scheduled load, not an optimized implementation.

## Run

From repository root:

```sh
python3 experiments/architecture_benchmark.py --seed 42 --messages 200 --horizon 30 --deadline 10
python3 -m unittest discover -s experiments -p 'test_*.py' -v
```

`docs/task002-results.json` is the deterministic output from the default run. No external packages, accounts, hardware, paid services or chain deployments required. The existing GitHub Actions workflow's test discovery should include the new tests automatically.

## Results (synthetic, fixed parameters)

| Scenario | Single attempt | Bounded retry | Store-and-forward | Dual path |
|---|---:|---:|---:|---:|
| Nominal | 97.5% | 100% | 100% | 100% |
| Lossy primary | 56.5% | 94.5% | 94.5% | 100% |
| Temporary shared partition | 0% | 0% | 0% | 0% |
| Primary path outage | 0% | 0% | 0% | 100% |
| Full partition | 0% | 0% | 0% | 0% |

Percentages are **delivery before tick 10**, not eventual delivery. In the temporary shared partition scenario, persistent policies deliver all messages after the partition clears at tick 12, but none meet the original deadline. In the full partition, no policy delivers by tick 30.

## What this establishes

The test harness reproduces expected qualitative tradeoffs in a simplified setting. It does **not** establish real-world network reliability or compare L1 consensus architectures. The dual-path policy assumes the backup is truly independent, available and affordable, which may not hold in practice. An asynchronous relay cannot guarantee settlement finality during a network partition.

## Task 002 decision gate

Do **not** select a dedicated L1 based on this benchmark. Next steps: (1) model finite queue capacity, bandwidth, traffic bursts and message expiry; (2) measure real or emulated network traces, including link-correlated failures; (3) compare integration with existing blockchain transaction broadcasting and actual finality proofs; (4) define separate, formally reviewed consensus and cross-domain security requirements. An authorized satellite-terminal trial should follow only once those test plans are documented.
