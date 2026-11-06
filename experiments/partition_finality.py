"""Educational quorum/partition model. NOT a consensus protocol or blockchain."""
from dataclasses import dataclass
from itertools import combinations


@dataclass(frozen=True)
class Scenario:
    validators: int
    reachable: int
    faulty: int = 0


def quorum(n: int) -> int:
    if n < 1:
        raise ValueError('validator count must be positive')
    return (2 * n) // 3 + 1


def quorum_available(s: Scenario) -> bool:
    if not (0 <= s.faulty <= s.reachable <= s.validators):
        raise ValueError('invalid scenario')
    return s.reachable - s.faulty >= quorum(s.validators)


def intersection_lower_bound(n: int) -> int:
    """Minimum intersection of two quorums drawn from the same n members."""
    q = quorum(n)
    return 2 * q - n


def simulate_partitions(n: int, partitions: tuple[int, ...]) -> dict:
    if not partitions or any(p < 0 for p in partitions) or sum(partitions) != n:
        raise ValueError('partitions must be nonnegative and sum to n')
    q = quorum(n)
    return {'validators': n, 'quorum': q, 'partitions': list(partitions),
            'quorum_capable_partitions': [i for i, p in enumerate(partitions) if p >= q],
            'quorum_intersection_min': intersection_lower_bound(n)}


def sweep(n: int) -> list[dict]:
    return [simulate_partitions(n, (a, n-a)) for a in range(n+1)]


if __name__ == '__main__':
    import json
    print(json.dumps({'model': 'static membership quorum arithmetic only',
                      'seven_validator_sweep': sweep(7)}, indent=2))
