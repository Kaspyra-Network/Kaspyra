import unittest
from partition_finality import Scenario, quorum, quorum_available, intersection_lower_bound, simulate_partitions, sweep


class PartitionModelTests(unittest.TestCase):
    def test_quorum(self):
        self.assertEqual(quorum(4), 3)
        self.assertEqual(quorum(7), 5)

    def test_reject_empty(self):
        with self.assertRaises(ValueError): quorum(0)

    def test_full_connectivity(self):
        self.assertTrue(quorum_available(Scenario(7, 7)))

    def test_minority_stalls(self):
        self.assertFalse(quorum_available(Scenario(7, 3)))

    def test_majority_threshold(self):
        self.assertTrue(quorum_available(Scenario(7, 5)))

    def test_faulty_members_do_not_vote(self):
        self.assertFalse(quorum_available(Scenario(7, 5, 1)))

    def test_invalid_fault_count(self):
        with self.assertRaises(ValueError): quorum_available(Scenario(7, 3, 4))

    def test_quorum_intersection(self):
        self.assertEqual(intersection_lower_bound(7), 3)

    def test_partition(self):
        result = simulate_partitions(7, (5, 2))
        self.assertEqual(result['quorum_capable_partitions'], [0])

    def test_split_stalls(self):
        self.assertEqual(simulate_partitions(7, (4, 3))['quorum_capable_partitions'], [])

    def test_invalid_partition(self):
        with self.assertRaises(ValueError): simulate_partitions(7, (3, 3))

    def test_at_most_one_partition_with_quorum(self):
        for result in sweep(7):
            self.assertLessEqual(len(result['quorum_capable_partitions']), 1)


if __name__ == '__main__':
    unittest.main()
