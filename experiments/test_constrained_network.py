"""Task 003 unit and invariant tests; compatible with unittest discovery."""
import unittest
from constrained_network import Config, benchmark, simulate, dropped


class ConstrainedNetworkTests(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(simulate(Config()), simulate(Config()))

    def test_accounting(self):
        for result in benchmark()['cases'].values():
            self.assertEqual(result['created'], result['delivered'] + result['expired'] + result['overflow'] + result['pending'])
            self.assertLessEqual(result['peak_queue'], result['parameters']['queue_limit'])

    def test_zero_capacity_during_full_outage(self):
        c = Config(ticks=10, arrival_ticks=5, arrivals_per_tick=2, capacity=2,
                   outage_start=0, outage_end=10, ttl=20)
        r = simulate(c)
        self.assertEqual(r['delivered'], 0)
        self.assertEqual(r['attempts'], 0)

    def test_backup_preserves_delivery_during_primary_outage(self):
        c = Config(ticks=10, arrival_ticks=5, arrivals_per_tick=2,
                   outage_start=0, outage_end=10, backup_enabled=True,
                   correlated_outage=False, loss_pct=0)
        self.assertGreater(simulate(c)['delivered'], 0)
        self.assertEqual(simulate(Config(**{**vars(c), 'correlated_outage': True}))['delivered'], 0)

    def test_overflow(self):
        r = simulate(Config(ticks=12, arrival_ticks=10, arrivals_per_tick=10,
                            queue_limit=3, capacity=1, outage_start=0, outage_end=12))
        self.assertGreater(r['overflow'], 0)
        self.assertLessEqual(r['peak_queue'], 3)

    def test_expiry(self):
        r = simulate(Config(ticks=12, arrival_ticks=3, arrivals_per_tick=2,
                            ttl=2, outage_start=0, outage_end=12))
        self.assertGreater(r['expired'], 0)
        self.assertEqual(r['delivered'], 0)

    def test_priority_changes_who_delivers_first(self):
        base = dict(ticks=1, arrival_ticks=1, arrivals_per_tick=8, capacity=2,
                    queue_limit=8, outage_start=1, outage_end=1, loss_pct=0)
        fifo = simulate(Config(**base))
        priority = simulate(Config(**base, scheduling='priority'))
        self.assertEqual(fifo['delivered'], priority['delivered'])
        self.assertEqual(priority['delivered_by_priority'][1], 2)
        self.assertEqual(fifo['delivered_by_priority'][1], 1)

    def test_no_messages_after_expiry(self):
        r = simulate(Config(ticks=10, arrival_ticks=1, arrivals_per_tick=3,
                            ttl=1, outage_start=0, outage_end=5))
        self.assertEqual(r['delivered'], 0)

    def test_loss_deterministic(self):
        self.assertEqual(dropped(42, 2, 3, 'primary', 50), dropped(42, 2, 3, 'primary', 50))
        self.assertFalse(dropped(42, 2, 3, 'primary', 0))
        self.assertTrue(dropped(42, 2, 3, 'primary', 100))

    def test_invalid_configuration(self):
        for cfg in (Config(queue_limit=0), Config(loss_pct=101), Config(scheduling='random')):
            with self.assertRaises(ValueError):
                simulate(cfg)


if __name__ == '__main__':
    unittest.main()
