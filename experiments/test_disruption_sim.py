import unittest
from disruption_sim import delivered, run
import random


class DeliveryTests(unittest.TestCase):
    def test_full_partition_prevents_delivery(self):
        self.assertFalse(delivered(random.Random(1), loss=0, outage=[(0, 10)], attempts=5))

    def test_no_loss_no_outage_delivers(self):
        self.assertTrue(delivered(random.Random(1), loss=0, outage=[], attempts=1))

    def test_outage_can_be_recovered_by_retry(self):
        self.assertTrue(delivered(random.Random(1), loss=0, outage=[(0, 4)], attempts=5))
        self.assertFalse(delivered(random.Random(1), loss=0, outage=[(0, 4)], attempts=1))

    def test_reproducible(self):
        self.assertEqual(run(42, 100), run(42, 100))

    def test_invalid_trial_count(self):
        with self.assertRaises(ValueError):
            run(trials=0)

    def test_partition_zero_successes(self):
        result = run(42, 100)['scenarios']['full_partition']
        self.assertEqual(result['single_attempt']['delivered'], 0)
        self.assertEqual(result['bounded_retry']['delivered'], 0)


if __name__ == '__main__':
    unittest.main()
