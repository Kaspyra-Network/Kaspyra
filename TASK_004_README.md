# KASPYRA — Task 004: Latency, Acknowledgments, and Fair Capacity

**Status:** Synthetic research experiment, not a deployed network. No satellite measurements, blockchain consensus, cryptographic proofs, or transaction finality.

## Objective
Compare transport policies under identical aggregate message-attempt capacity (four attempts per tick), synthetic one-way latency, ACK latency, data/ACK loss, and primary-path outage. Forty deterministic seeds give an illustrative distribution of outcomes. The normal-approximation 95% intervals summarize *seed variation under this model*, not real-world confidence about satellites.

## Strategies
- `fire_once`: attempts at most once; drops messages created during primary outage.
- `retry`: retains messages, retransmits on timeout until ACK or TTL.
- `store_forward`: **currently behaviorally equivalent to retry**; kept as a named hypothesis for future durable-storage/restart experiments, not independent evidence of advantage.
- `dual_path`: uses a modeled independent backup path during primary outage and alternates on retransmissions. The **aggregate capacity remains four attempts/tick**, but the backup path's real-world capital/operating costs are not modeled.

All strategies use the same synthetic packet loss and propagation delay distributions. Duplicate deliveries are suppressed by message ID, but duplicate arrivals and ACKs are counted. Delivery and ACK rates are distinct; neither represents consensus finality. In-flight deliveries can arrive after the final observation tick and are excluded.

## Run
From the repository root:

```sh
python -m unittest discover -s experiments -p 'test_*.py' -v
python experiments/latency_ack_benchmark.py --trials 40
```

The committed baseline output is `docs/task004-results.json`. No dependencies beyond Python 3.11+ standard library.

## Interpretation limits and next decision gate
This is a discrete-tick toy model with fixed packet sizes, constant latencies, idealized independent backup, no path setup costs, no contention between users, no adversarial relays, no persistent disk, and no actual chain transaction confirmation. A higher synthetic delivery rate does **not** justify a new L1 or a claim of satellite reliability.

**Next:** vary RTT, bandwidth, correlated failures, backup costs and restart durability; compare an existing-chain relay design against a dedicated L1 only when a specific consensus or settlement requirement is demonstrably unmet.

## Publishing
Upload `experiments/latency_ack_benchmark.py`, `experiments/test_latency_ack_benchmark.py`, `docs/task004-results.json`, and `TASK_004_README.md` into the existing repository preserving their paths. Do not delete Tasks 001–003. GitHub Actions should run unittest discovery over `experiments/`.
