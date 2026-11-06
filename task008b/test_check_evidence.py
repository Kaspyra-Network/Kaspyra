import unittest
from check_evidence import validate

class EvidenceTests(unittest.TestCase):
    def fixture(self):
        return dict(cometbft_version='v0.x.y', commit='abc', ci_run_url='https://example.invalid', nodes=[{'height':3,'app_hash':'abc'} for _ in range(4)],transfer_tx_hash='tx',quorum_loss=True,quorum_recovery=True,restart=True,crash_replay=True)
    def test_accepts_shape(self):
        self.assertTrue(validate(self.fixture()))
    def test_rejects_mismatch(self):
        d=self.fixture();d['nodes'][0]['app_hash']='def'
        with self.assertRaises(ValueError): validate(d)
    def test_rejects_missing(self):
        d=self.fixture();del d['restart']
        with self.assertRaises(ValueError): validate(d)
    def test_rejects_incomplete_recovery(self):
        d=self.fixture();d['quorum_loss']=False
        with self.assertRaises(ValueError): validate(d)

if __name__=='__main__': unittest.main()
