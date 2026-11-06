#!/usr/bin/env python3
"""Deterministic synthetic message-delivery experiment; NOT a satellite or blockchain model."""
import argparse
import json
import random


def delivered(rng, *, loss, outage, attempts, deadline=10, interval=2):
    """Whether a message arrives before deadline under simple synthetic conditions."""
    for i in range(attempts):
        t = i * interval
        if t >= deadline:
            break
        if any(start <= t < end for start, end in outage):
            continue
        if rng.random() >= loss:
            return True
    return False


def run(seed=42, trials=200):
    if trials <= 0:
        raise ValueError('trials must be positive')
    scenarios = {
        'clear': {'loss': 0.02, 'outage': []},
        'lossy': {'loss': 0.45, 'outage': []},
        'initial_outage': {'loss': 0.15, 'outage': [(0, 4)]},
        'full_partition': {'loss': 0.0, 'outage': [(0, 10)]},
    }
    result = {'seed': seed, 'trials_per_policy_per_scenario': trials, 'synthetic': True, 'scenarios': {}}
    for index, (name, config) in enumerate(scenarios.items()):
        policies = {}
        for pidx, (policy, attempts) in enumerate((('single_attempt', 1), ('bounded_retry', 5))):
            rng = random.Random(seed + index * 1000003 + pidx * 99991)
            successes = sum(delivered(rng, attempts=attempts, **config) for _ in range(trials))
            policies[policy] = {'delivered': successes, 'rate': round(successes / trials, 4)}
        result['scenarios'][name] = policies
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--trials', type=int, default=200)
    args = parser.parse_args()
    print(json.dumps(run(args.seed, args.trials), indent=2))
