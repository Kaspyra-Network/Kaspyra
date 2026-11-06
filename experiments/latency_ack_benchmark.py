"""Task 004: synthetic equal-budget, ACK-aware discrete-time message transport.

No consensus, blockchain finality, measured satellite traces, or cryptographic proofs.
"""
from dataclasses import dataclass, asdict
import argparse
import hashlib
import json
import math
import statistics


def random_unit(seed, *parts):
    raw = ':'.join(map(str, (seed, *parts))).encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], 'big') / 2**64


@dataclass(frozen=True)
class Config:
    ticks: int = 90
    arrivals: int = 36
    rate: int = 3
    capacity: int = 4  # shared attempts per tick across ALL paths
    latency: int = 3  # one-way, in ticks
    ack_latency: int = 3  # one-way, in ticks
    timeout: int = 8
    ttl: int = 65
    queue_limit: int = 150
    loss: float = 0.12
    ack_loss: float = 0.08
    outage_start: int = 12
    outage_end: int = 28
    seed: int = 0
    strategy: str = 'retry'  # fire_once, retry, store_forward, dual_path

    def validate(self):
        if min(self.ticks, self.arrivals, self.rate, self.capacity, self.latency,
               self.ack_latency, self.timeout, self.ttl, self.queue_limit) <= 0:
            raise ValueError('positive dimensions required')
        if self.arrivals > self.ticks or not 0 <= self.outage_start <= self.outage_end <= self.ticks:
            raise ValueError('invalid time ranges')
        if not 0 <= self.loss <= 1 or not 0 <= self.ack_loss <= 1:
            raise ValueError('loss probabilities outside [0,1]')
        if self.strategy not in ('fire_once', 'retry', 'store_forward', 'dual_path'):
            raise ValueError('unknown strategy')


def run(cfg):
    cfg.validate()
    # send and ACK events are scheduled, never delivered instantaneously.
    events = {}  # tick -> list of (kind, id, attempt, path)
    pending = {}  # id -> state
    received = set()
    acknowledged = set()
    attempts = duplicates = accepted = overflow = expired = ack_events = 0
    first_receive_delay = []
    first_ack_delay = []
    def schedule(tick, event):
        events.setdefault(tick, []).append(event)

    for tick in range(cfg.ticks):
        # process deliveries and ACKs; late events may arrive after message expiry
        for kind, mid, attempt, path in events.pop(tick, []):
            st = pending[mid]
            if kind == 'receive':
                if tick - st['created'] >= cfg.ttl:
                    continue
                if mid in received:
                    duplicates += 1
                else:
                    received.add(mid)
                    first_receive_delay.append(tick - st['created'])
                if random_unit(cfg.seed, 'ackloss', mid, attempt, path) >= cfg.ack_loss:
                    schedule(tick + cfg.ack_latency, ('ack', mid, attempt, path))
            else:
                ack_events += 1
                if mid not in acknowledged:
                    acknowledged.add(mid)
                    first_ack_delay.append(tick - st['created'])
        if tick < cfg.arrivals:
            for index in range(cfg.rate):
                mid = tick * cfg.rate + index
                # Queue bound counts not-yet-received messages; unacked entries also consume slots.
                active = sum(1 for v in pending.values() if not v['closed'])
                if active >= cfg.queue_limit:
                    overflow += 1
                else:
                    pending[mid] = dict(created=tick, last=-10**9, sent=0, closed=False)
                    accepted += 1
        for mid, st in pending.items():
            if not st['closed'] and tick - st['created'] >= cfg.ttl:
                st['closed'] = True
                if mid not in received:
                    expired += 1
            if mid in acknowledged:
                st['closed'] = True
        # Same aggregate capacity for every strategy. Dual path uses alternation,
        # not extra bandwidth. No claim that a second path is free in reality.
        budget = cfg.capacity
        for mid, st in pending.items():
            if budget == 0:
                break
            if st['closed']:
                continue
            if st['sent'] and (cfg.strategy == 'fire_once' or tick - st['last'] < cfg.timeout):
                continue
            primary_down = cfg.outage_start <= tick < cfg.outage_end
            if cfg.strategy == 'dual_path':
                path = 'backup' if primary_down else ('backup' if st['sent'] % 2 else 'primary')
            else:
                path = 'primary'
            if primary_down and path == 'primary':
                if cfg.strategy == 'fire_once' and not st['sent']:
                    # fire-and-forget drops when unavailable, unlike store-and-forward
                    st['sent'] = 1
                    st['closed'] = True
                elif cfg.strategy == 'retry' and not st['sent']:
                    # retry queues until connection returns, same as store_forward
                    pass
                continue
            attempt = st['sent']
            st['sent'] += 1
            st['last'] = tick
            attempts += 1
            budget -= 1
            # backup has identical synthetic loss and latency distribution
            if random_unit(cfg.seed, 'data', mid, attempt, path) >= cfg.loss:
                schedule(tick + cfg.latency, ('receive', mid, attempt, path))
    created = cfg.arrivals * cfg.rate
    return {
        'created': created, 'accepted': accepted, 'overflow': overflow,
        'received_unique': len(received), 'acknowledged_unique': len(acknowledged),
        'expired_without_receipt': expired, 'pending_unreceived': sum(
            1 for mid in pending if mid not in received and not pending[mid]['closed']),
        'attempts': attempts, 'duplicates_received': duplicates,
        'ack_events': ack_events,
        'delivery_rate': len(received) / created,
        'ack_rate': len(acknowledged) / created,
        'mean_receive_delay': statistics.mean(first_receive_delay) if first_receive_delay else None,
        'mean_ack_delay': statistics.mean(first_ack_delay) if first_ack_delay else None,
    }


def ci95(values):
    mean = statistics.mean(values)
    if len(values) < 2:
        return [mean, mean]
    margin = 1.96 * statistics.stdev(values) / math.sqrt(len(values))
    return [max(0.0, mean - margin), min(1.0, mean + margin)]


def benchmark(trials=40):
    if trials < 2:
        raise ValueError('at least two trials required')
    out = {}
    for strategy in ('fire_once', 'retry', 'store_forward', 'dual_path'):
        samples = [run(Config(seed=i, strategy=strategy)) for i in range(trials)]
        delivery = [s['delivery_rate'] for s in samples]
        ack = [s['ack_rate'] for s in samples]
        out[strategy] = {
            'mean_delivery_rate': statistics.mean(delivery),
            'delivery_ci95_normal_approx': ci95(delivery),
            'mean_ack_rate': statistics.mean(ack),
            'ack_ci95_normal_approx': ci95(ack),
            'mean_attempts': statistics.mean(s['attempts'] for s in samples),
            'mean_duplicates': statistics.mean(s['duplicates_received'] for s in samples),
        }
    return {'synthetic': True, 'trials': trials, 'shared_attempt_capacity_per_tick': Config.capacity,
            'limitations': 'Normal-approximation intervals across deterministic pseudo-random seeds; no measured satellite traces or consensus/finality',
            'strategies': out}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--trials', type=int, default=40)
    args = parser.parse_args()
    print(json.dumps(benchmark(args.trials), indent=2))
