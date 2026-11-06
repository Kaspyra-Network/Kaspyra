# Experiment 001 — Synthetic message delivery

This **local-only** Python standard-library simulator compares one attempt against bounded store-and-forward retries under synthetic packet loss, delay and scheduled outage windows. It does not simulate blockchain consensus, transactions, finality, actual satellite radio links, pricing or geographic coverage.

Run:

```sh
python3 -m unittest discover -s experiments -p 'test_*.py' -v
python3 experiments/disruption_sim.py --seed 42 --trials 200
```

A message is counted as delivered if at least one attempt succeeds before a fixed deadline. Retries use independent pseudorandom packet drops; attempts during outage windows fail. No throughput contention, ACK loss, adversarial behavior or queue storage failures are modeled. Results are illustrative and should not be generalized to real networks.
