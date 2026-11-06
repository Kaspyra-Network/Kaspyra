import unittest
from kaspyra_local_chain import Ledger, address, new_identity, signed_transfer, verify_transfer, run_demo

class LocalChainTests(unittest.TestCase):
    def setUp(self):
        self.private, self.public, self.sender = new_identity()
        _, _, self.recipient = new_identity()
        self.ledger = Ledger({self.sender: 1000, self.recipient: 0})

    def tx(self, amount=125, nonce=0):
        return signed_transfer(self.private, self.public, self.recipient, amount, nonce)

    def test_valid_signature(self):
        self.assertTrue(verify_transfer(self.tx()))

    def test_tampered_amount_rejected(self):
        tx = self.tx(); tx['payload']['amount'] = 900
        self.assertFalse(verify_transfer(tx))

    def test_tampered_recipient_rejected(self):
        tx = self.tx(); tx['payload']['to'] = self.sender
        self.assertFalse(verify_transfer(tx))

    def test_chain_replay_rejected(self):
        tx = self.tx(); tx['payload']['chain_id'] = 'another-chain'
        self.assertFalse(verify_transfer(tx))

    def test_valid_transfer(self):
        self.assertTrue(self.ledger.apply(self.tx())[0]); self.assertEqual(self.ledger.balances[self.recipient], 125)

    def test_replay_nonce_rejected(self):
        tx = self.tx(); self.ledger.apply(tx)
        self.assertFalse(self.ledger.apply(tx)[0])

    def test_insufficient_balance(self):
        self.assertFalse(self.ledger.apply(self.tx(1001))[0])

    def test_zero_and_negative_amounts(self):
        self.assertFalse(verify_transfer(self.tx(0)))
        self.assertFalse(verify_transfer(self.tx(-1)))

    def test_bool_amount_rejected(self):
        self.assertFalse(verify_transfer(self.tx(True)))

    def test_invalid_nonce(self):
        self.assertFalse(self.ledger.apply(self.tx(nonce=1))[0])

    def test_deterministic_digest(self):
        a = Ledger({self.sender: 1000, self.recipient: 0}); b = Ledger({self.sender: 1000, self.recipient: 0})
        tx = self.tx(); a.apply(tx); b.apply(tx)
        self.assertEqual(a.digest(), b.digest())

    def test_distinct_digest_after_transfer(self):
        before = self.ledger.digest(); self.ledger.apply(self.tx())
        self.assertNotEqual(before, self.ledger.digest())

    def test_four_process_execution(self):
        self.assertEqual(run_demo()['matching_state_digests'], 4)

if __name__ == '__main__':
    unittest.main()
