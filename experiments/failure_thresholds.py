"""Task 005: reproducible stress sweep of Task 004's synthetic transport model.

Requires experiments/latency_ack_benchmark.py from Task 004 in same directory.
This is not a satellite measurement, consensus simulation, or blockchain client.
"""
import argparse
import dataclasses
import json
import statistics
from latency_ack_benchmark import Config, run

STRATEGIES = ('fire_once', 'retry', 'store_forward', 'dual_path')
# One variable changed per scenario; capacity is an aggregate attempt budget.
SCENARIOS = {
    'baseline': {},
    'capacity_1': {'capacity': 1},
    'capacity_2': {'capacity': 2},
    'capacity_6': {'capacity': 6},
    'queue_12': {'queue_limit': 12},
    'queue_32': {'queue_limit': 32},
    'ttl_12': {'ttl': 12},
    'ttl_24': {'ttl': 24},
    'loss_40pct': {'loss': 0.40},
    'loss_70pct': {'loss': 0.70},
    'outage_40ticks': {'outage_start': 8, 'outage_end': 48},
    'outage_70ticks': {'outage_start': 8, 'outage_end': 78},
    'ack_loss_60pct': {'ack_loss': 0.60},
    'roundtrip_20ticks': {'latency': 10, 'ack_latency': 10, 'timeout': 22},
}


def evaluate(trials=30):
    if not isinstance(trials, int) or trials < 2:
        raise ValueError('trials must be >= 2')
    result = {'synthetic': True, 'trials_per_cell': trials,
              'capacity_basis': 'equal aggregate attempts per tick, not equal physical infrastructure cost',
              'scenarios': {}, 'caveats': [
                  'Task 004 retry and store_forward are functionally equivalent in this model.',
                  'Dual path assumes backup available during primary outage; no shared-fate failure modeled.',
                  'Queue memory, congestion, ACK and expiry semantics are simplified.',
                  'Received means delivered to a simulated receiver, not blockchain inclusion or finality.',
                  'Seed-to-seed variability is simulated, not a statistical sample of satellite conditions.',
              ]}
    for scenario, overrides in SCENARIOS.items():
        rows = {}
        for strategy in STRATEGIES:
            samples = [run(dataclasses.replace(Config(), strategy=strategy, seed=seed, **overrides))
                       for seed in range(trials)]
            rows[strategy] = {
                'delivery_mean': round(statistics.mean(x['delivery_rate'] for x in samples), 5),
                'ack_mean': round(statistics.mean(x['ack_rate'] for x in samples), 5),
                'overflow_mean': round(statistics.mean(x['overflow'] for x in samples), 2),
                'expired_mean': round(statistics.mean(x['expired_without_receipt'] for x in samples), 2),
                'attempts_mean': round(statistics.mean(x['attempts'] for x in samples), 2),
                'duplicate_receipts_mean': round(statistics.mean(x['duplicates_received'] for x in samples), 2),
            }
        result['scenarios'][scenario] = {'overrides': overrides, 'strategies': rows}
    return result


def decision(result):
    rows = result['scenarios']
    return {
        'rule': 'No new L1 recommendation from transport-only experiments',
        'retry_store_forward_equivalent_in_all_cells': all(
            rows[s]['strategies']['retry'] == rows[s]['strategies']['store_forward'] for s in rows),
        'threshold_examples': {s: {
            'retry_delivery': rows[s]['strategies']['retry']['delivery_mean'],
            'dual_delivery': rows[s]['strategies']['dual_path']['delivery_mean'],
        } for s in ('baseline', 'capacity_1', 'queue_12', 'ttl_12', 'outage_70ticks')},
        'next_gate': 'Integrate with local real blockchain node; measure inclusion/finality separately, plus physical transport traces and shared-fate backup failures',
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--trials', type=int, default=30)
    args = parser.parse_args()
    result = evaluate(args.trials)
    result['decision'] = decision(result)
    print(json.dumps(result, indent=2, sort_keys=True))
