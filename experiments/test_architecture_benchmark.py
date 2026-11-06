import unittest
from architecture_benchmark import evaluate, schedule, send, SCENARIOS


class ArchitectureBenchmarkTests(unittest.TestCase):
    def test_determinism(self):
        self.assertEqual(evaluate(), evaluate())

    def test_no_delivery_in_full_partition(self):
        result = evaluate()["scenarios"]["full_partition"]
        for policy in result.values():
            self.assertEqual(policy["eventually_delivered"], 0)

    def test_no_success_during_shared_partition(self):
        for path in ("primary", "backup"):
            for tick in range(12):
                self.assertFalse(send(42, "temporary_partition", 0, path, tick))

    def test_store_forward_can_recover_after_partition(self):
        results = evaluate()["scenarios"]["temporary_partition"]
        self.assertEqual(results["bounded_retry"]["eventually_delivered"], 0)
        self.assertGreater(results["store_forward"]["eventually_delivered"], 0)
        self.assertEqual(results["store_forward"]["on_time"], 0)

    def test_dual_path_available_during_primary_outage(self):
        results = evaluate()["scenarios"]["primary_path_outage"]
        self.assertEqual(results["store_forward"]["on_time"], 0)
        self.assertGreater(results["dual_path"]["on_time"], 0)

    def test_unique_delivery_dedup(self):
        for scenario in evaluate()["scenarios"].values():
            for result in scenario.values():
                self.assertEqual(result["unique_deliveries"], result["eventually_delivered"])
                self.assertLessEqual(result["unique_deliveries"], 200)
                self.assertGreaterEqual(result["duplicate_arrivals_suppressed"], 0)

    def test_invalid_parameters(self):
        for kwargs in ({"messages": 0}, {"horizon": 0}, {"deadline": 0}, {"deadline": 31}):
            with self.assertRaises(ValueError):
                evaluate(**kwargs)

    def test_unknown_policy(self):
        with self.assertRaises(ValueError):
            schedule("invalid", 30)

    def test_single_attempt_count(self):
        self.assertEqual(evaluate()["scenarios"]["nominal"]["single_attempt"]["attempts"], 200)


if __name__ == "__main__":
    unittest.main()
