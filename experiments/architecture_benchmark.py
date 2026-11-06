"""KASPYRA Task 002: deterministic, synthetic transport-policy comparison.

Not a satellite measurement, consensus protocol, finality model or production relay.
All four policies see the same scenario, message IDs and path/time random draws.
"""
import argparse
import hashlib
import json

SCENARIOS = {
    "nominal": {"primary_loss": 0.02, "backup_loss": 0.02, "primary_outages": [], "backup_outages": []},
    "lossy_primary": {"primary_loss": 0.45, "backup_loss": 0.12, "primary_outages": [], "backup_outages": []},
    "temporary_partition": {"primary_loss": 0.10, "backup_loss": 0.10, "primary_outages": [[0, 12]], "backup_outages": [[0, 12]]},
    "primary_path_outage": {"primary_loss": 0.10, "backup_loss": 0.10, "primary_outages": [[0, 16]], "backup_outages": []},
    "full_partition": {"primary_loss": 0, "backup_loss": 0, "primary_outages": [[0, 40]], "backup_outages": [[0, 40]]},
}
POLICIES = ("single_attempt", "bounded_retry", "store_forward", "dual_path")


def random_draw(seed, scenario, message_id, path, tick):
    payload = f"{seed}|{scenario}|{message_id}|{path}|{tick}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big") / 2**64


def path_available(config, path, tick):
    return not any(start <= tick < end for start, end in config[f"{path}_outages"])


def send(seed, scenario, message_id, path, tick):
    config = SCENARIOS[scenario]
    return path_available(config, path, tick) and random_draw(seed, scenario, message_id, path, tick) >= config[f"{path}_loss"]


def schedule(policy, horizon):
    if policy == "single_attempt":
        return [(0, "primary")]
    if policy == "bounded_retry":
        return [(tick, "primary") for tick in (0, 3, 6, 9) if tick < horizon]
    if policy == "store_forward":
        return [(tick, "primary") for tick in range(0, horizon, 3)]
    if policy == "dual_path":
        return [(tick, path) for tick in range(0, horizon, 3) for path in ("primary", "backup")]
    raise ValueError(f"unknown policy: {policy}")


def evaluate(seed=42, messages=200, horizon=30, deadline=10):
    if messages <= 0 or horizon <= 0 or deadline <= 0 or deadline > horizon:
        raise ValueError("require messages > 0 and 0 < deadline <= horizon")
    result = {
        "metadata": {"seed": seed, "messages": messages, "horizon_ticks": horizon,
                     "deadline_ticks": deadline, "synthetic": True,
                     "scope": "message transport only; no satellite measurements, consensus or finality"},
        "scenarios": {},
    }
    for scenario in SCENARIOS:
        results = {}
        for policy in POLICIES:
            on_time = eventual = attempts = duplicate_deliveries = 0
            first_arrivals = []
            recovered_after_deadline = 0
            for message_id in range(messages):
                # We deliberately model repeated attempts, including potential duplicate arrivals;
                # the receiver deduplicates by authenticated-message ID (authentication not modeled).
                arrivals = []
                for tick, path in schedule(policy, horizon):
                    attempts += 1
                    if send(seed, scenario, message_id, path, tick):
                        arrivals.append(tick)
                if arrivals:
                    first = min(arrivals)
                    first_arrivals.append(first)
                    eventual += 1
                    on_time += first < deadline
                    recovered_after_deadline += first >= deadline
                    duplicate_deliveries += len(arrivals) - 1
            results[policy] = {
                "on_time": on_time, "eventually_delivered": eventual,
                "on_time_rate": round(on_time / messages, 4),
                "eventual_rate": round(eventual / messages, 4),
                "attempts": attempts,
                "attempts_per_message": round(attempts / messages, 2),
                "mean_first_arrival_ticks": round(sum(first_arrivals) / len(first_arrivals), 3) if first_arrivals else None,
                "recovered_after_deadline": recovered_after_deadline,
                "duplicate_arrivals_suppressed": duplicate_deliveries,
                "unique_deliveries": eventual,
            }
        result["scenarios"][scenario] = results
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--messages", type=int, default=200)
    parser.add_argument("--horizon", type=int, default=30)
    parser.add_argument("--deadline", type=int, default=10)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.seed, args.messages, args.horizon, args.deadline), indent=2))
