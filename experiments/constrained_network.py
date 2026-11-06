"""KASPYRA Task 003: deterministic discrete-tick constrained transport model.

Synthetic link capacities, queueing, expiry, correlated failures, and scheduling.
Not a satellite trace, cryptographic protocol, or blockchain finality model.
"""
import argparse
from collections import deque
from dataclasses import dataclass
import hashlib
import json


@dataclass(frozen=True)
class Message:
    mid: int
    created: int
    ttl: int
    priority: int  # 1=critical, 0=ordinary


@dataclass(frozen=True)
class Config:
    ticks: int = 50
    arrival_ticks: int = 20
    arrivals_per_tick: int = 8
    capacity: int = 5
    queue_limit: int = 40
    ttl: int = 20
    outage_start: int = 10
    outage_end: int = 22
    backup_capacity: int = 3
    backup_enabled: bool = False
    correlated_outage: bool = True
    scheduling: str = 'fifo'
    loss_pct: int = 0
    seed: int = 42

    def validate(self):
        if min(self.ticks, self.arrival_ticks, self.arrivals_per_tick, self.capacity,
               self.queue_limit, self.ttl) < 1:
            raise ValueError('positive ticks, arrivals, capacity, queue_limit, ttl required')
        if self.arrival_ticks > self.ticks or not 0 <= self.outage_start <= self.outage_end <= self.ticks:
            raise ValueError('invalid tick range')
        if self.backup_capacity < 0 or not 0 <= self.loss_pct <= 100:
            raise ValueError('invalid backup capacity or loss')
        if self.scheduling not in ('fifo', 'priority'):
            raise ValueError('scheduling must be fifo or priority')


def dropped(seed, mid, tick, path, loss_pct):
    # Independent, reproducible synthetic loss for each message/attempt/path.
    digest = hashlib.sha256(f'{seed}:{mid}:{tick}:{path}'.encode()).digest()
    return int.from_bytes(digest[:8], 'big') % 10000 < loss_pct * 100


def simulate(cfg: Config):
    cfg.validate()
    queue = []
    seen = set()
    created = accepted = overflow = expired = delivered = attempts = lost = 0
    delivered_priority = {0: 0, 1: 0}
    created_priority = {0: 0, 1: 0}
    delay_sum = 0
    peak_queue = 0
    recovery_backlog = 0
    delivered_after_outage = 0
    per_tick = []
    for tick in range(cfg.ticks):
        # Expiry is evaluated before transmission. TTL is measured from creation.
        survivors = []
        for m in queue:
            if tick - m.created >= m.ttl:
                expired += 1
            else:
                survivors.append(m)
        queue = survivors
        if tick < cfg.arrival_ticks:
            for index in range(cfg.arrivals_per_tick):
                mid = tick * cfg.arrivals_per_tick + index
                priority = int(index % 4 == 0)
                created += 1
                created_priority[priority] += 1
                if len(queue) >= cfg.queue_limit:
                    overflow += 1
                else:
                    queue.append(Message(mid, tick, cfg.ttl, priority))
                    accepted += 1
        peak_queue = max(peak_queue, len(queue))
        in_outage = cfg.outage_start <= tick < cfg.outage_end
        primary = 0 if in_outage else cfg.capacity
        backup = (cfg.backup_capacity if cfg.backup_enabled and (not in_outage or not cfg.correlated_outage) else 0)
        if tick == cfg.outage_end:
            recovery_backlog = len(queue)
        if cfg.scheduling == 'priority':
            queue.sort(key=lambda m: (-m.priority, m.created, m.mid))
        # Capacity is measured in message transmission attempts, not successful deliveries.
        sent_now = 0
        for path, budget in (('primary', primary), ('backup', backup)):
            for _ in range(min(budget, len(queue))):
                m = queue.pop(0)
                attempts += 1
                sent_now += 1
                if dropped(cfg.seed, m.mid, tick, path, cfg.loss_pct):
                    lost += 1
                    # Retry on a later tick, retaining original TTL and queue bound.
                    queue.append(m)
                else:
                    if m.mid in seen:
                        raise AssertionError('duplicate unique delivery')
                    seen.add(m.mid)
                    delivered += 1
                    delivered_priority[m.priority] += 1
                    delay_sum += tick - m.created
                    if tick >= cfg.outage_end and cfg.outage_end > cfg.outage_start:
                        delivered_after_outage += 1
        per_tick.append({'tick': tick, 'queue_end': len(queue), 'attempts': sent_now,
                         'delivered_cumulative': delivered})
    # Messages left in the queue are neither delivered nor dropped by expiry/overflow.
    pending = len(queue)
    assert created == overflow + expired + delivered + pending
    return {
        'parameters': vars(cfg), 'synthetic': True,
        'created': created, 'accepted': accepted, 'delivered': delivered,
        'delivery_rate': round(delivered / created, 4),
        'overflow': overflow, 'expired': expired, 'pending': pending,
        'attempts': attempts, 'loss_attempts': lost,
        'peak_queue': peak_queue, 'recovery_backlog': recovery_backlog,
        'delivered_after_outage_end': delivered_after_outage,
        'mean_delay_ticks': round(delay_sum / delivered, 3) if delivered else None,
        'created_by_priority': created_priority,
        'delivered_by_priority': delivered_priority,
        'per_tick': per_tick,
    }


def benchmark():
    base = dict(ticks=60, arrival_ticks=25, arrivals_per_tick=6, capacity=5,
                queue_limit=60, ttl=30, outage_start=10, outage_end=22,
                backup_capacity=3, loss_pct=5, seed=42)
    cases = {
        'primary_fifo': Config(**base),
        'primary_priority': Config(**base, scheduling='priority'),
        'independent_backup': Config(**base, backup_enabled=True, correlated_outage=False),
        'correlated_backup': Config(**base, backup_enabled=True, correlated_outage=True),
        'tight_queue': Config(**{**base, 'queue_limit': 15}),
        'short_ttl': Config(**{**base, 'ttl': 8}),
    }
    return {'status': 'synthetic transport model, not a real network measurement',
            'cases': {name: simulate(config) for name, config in cases.items()}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--benchmark', action='store_true', help='run fixed six-case comparison')
    args = parser.parse_args()
    print(json.dumps(benchmark() if args.benchmark else simulate(Config()), indent=2))
