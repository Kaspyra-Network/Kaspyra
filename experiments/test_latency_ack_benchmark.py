import unittest
from latency_ack_benchmark import Config, run, benchmark, ci95


class Task004Tests(unittest.TestCase):
    def test_repeatability(self):
        self.assertEqual(run(Config()), run(Config()))

    def test_equal_capacity(self):
        for strategy in ('fire_once', 'retry', 'store_forward', 'dual_path'):
            r = run(Config(strategy=strategy, loss=0, ack_loss=0, outage_start=0, outage_end=0))
            self.assertLessEqual(r['attempts'], Config.ticks * Config.capacity)

    def test_ack_after_receipt(self):
        r = run(Config(loss=0, ack_loss=0, outage_start=0, outage_end=0))
        self.assertLessEqual(r['acknowledged_unique'], r['received_unique'])
        self.assertGreaterEqual(r['mean_ack_delay'], r['mean_receive_delay'])

    def test_full_outage(self):
        r = run(Config(ticks=40, arrivals=10, outage_start=0, outage_end=40, strategy='store_forward'))
        self.assertEqual(r['received_unique'], 0)

    def test_backup_during_primary_outage(self):
        c = Config(ticks=40, arrivals=10, outage_start=0, outage_end=40, strategy='dual_path', loss=0)
        self.assertGreater(run(c)['received_unique'], 0)

    def test_duplicate_suppression(self):
        r = run(Config(timeout=1, latency=4, ack_latency=4, loss=0, ack_loss=0, outage_start=0, outage_end=0))
        self.assertGreater(r['duplicates_received'], 0)
        self.assertLessEqual(r['received_unique'], r['created'])

    def test_expiry(self):
        r = run(Config(ttl=2, latency=4, outage_start=0, outage_end=0))
        self.assertEqual(r['received_unique'], 0)

    def test_bounded_queue(self):
        r = run(Config(queue_limit=2, outage_start=0, outage_end=40, ticks=40, arrivals=10))
        self.assertGreater(r['overflow'], 0)

    def test_ci(self):
        self.assertEqual(ci95([0.5, 0.5]), [0.5, 0.5])

    def test_benchmark(self):
        b = benchmark(3)
        self.assertEqual(len(b['strategies']), 4)
        for s in b['strategies'].values():
            self.assertTrue(0 <= s['mean_delivery_rate'] <= 1)

    def test_validation(self):
        with self.assertRaises(ValueError):
            run(Config(capacity=0))
        with self.assertRaises(ValueError):
            benchmark(1)


if __name__ == '__main__':
    unittest.main()
