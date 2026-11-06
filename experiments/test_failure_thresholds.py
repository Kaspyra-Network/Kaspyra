import unittest
from failure_thresholds import SCENARIOS, STRATEGIES, evaluate, decision


class FailureThresholdTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = evaluate(2)

    def test_scenarios_present(self):
        self.assertEqual(set(self.data['scenarios']), set(SCENARIOS))

    def test_strategy_coverage(self):
        for case in self.data['scenarios'].values():
            self.assertEqual(set(case['strategies']), set(STRATEGIES))

    def test_rates_bounded(self):
        for case in self.data['scenarios'].values():
            for row in case['strategies'].values():
                for field in ('delivery_mean', 'ack_mean'):
                    self.assertGreaterEqual(row[field], 0)
                    self.assertLessEqual(row[field], 1)

    def test_retry_and_store_forward_equivalence(self):
        self.assertTrue(decision(self.data)['retry_store_forward_equivalent_in_all_cells'])

    def test_deterministic(self):
        self.assertEqual(self.data, evaluate(2))

    def test_invalid_trials(self):
        with self.assertRaises(ValueError):
            evaluate(1)

    def test_congestion_reduces_delivery(self):
        b = self.data['scenarios']['baseline']['strategies']['retry']['delivery_mean']
        c = self.data['scenarios']['capacity_1']['strategies']['retry']['delivery_mean']
        self.assertLess(c, b)

    def test_no_consensus_claim(self):
        self.assertIn('not blockchain inclusion or finality', ' '.join(self.data['caveats']))


if __name__ == '__main__':
    unittest.main()
