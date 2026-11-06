"""Task 007: local deterministic execution prototype, NOT a consensus protocol."""
import hashlib
import json
import multiprocessing as mp

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def address(public_key_bytes):
    return hashlib.sha256(public_key_bytes).hexdigest()[:40]


def new_identity():
    private = Ed25519PrivateKey.generate()
    pub = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return private, pub, address(pub)


def signed_transfer(private, pub, recipient, amount, nonce, chain_id='kaspyra-local-007'):
    payload = {'chain_id': chain_id, 'from': address(pub), 'to': recipient, 'amount': amount, 'nonce': nonce}
    return {'payload': payload, 'public_key': pub.hex(), 'signature': private.sign(canonical(payload)).hex()}


def verify_transfer(tx, expected_chain='kaspyra-local-007'):
    try:
        payload = tx['payload']
        if set(payload) != {'chain_id', 'from', 'to', 'amount', 'nonce'}:
            return False
        if payload['chain_id'] != expected_chain or not isinstance(payload['amount'], int) or isinstance(payload['amount'], bool) or payload['amount'] <= 0:
            return False
        if not isinstance(payload['nonce'], int) or isinstance(payload['nonce'], bool) or payload['nonce'] < 0:
            return False
        if not isinstance(payload['to'], str) or len(payload['to']) != 40 or any(c not in '0123456789abcdef' for c in payload['to']):
            return False
        pub = bytes.fromhex(tx['public_key'])
        if address(pub) != payload['from']:
            return False
        Ed25519PublicKey.from_public_bytes(pub).verify(bytes.fromhex(tx['signature']), canonical(payload))
        return True
    except (ValueError, KeyError, TypeError, AttributeError, InvalidSignature):
        return False


class Ledger:
    def __init__(self, balances):
        self.balances = dict(balances)
        self.nonces = {a: 0 for a in balances}
        self.height = 0
        self.history = []

    def apply(self, tx):
        if not verify_transfer(tx):
            return False, 'invalid signature or transaction'
        p = tx['payload']
        sender, recipient, amount = p['from'], p['to'], p['amount']
        if self.nonces.get(sender, 0) != p['nonce']:
            return False, 'nonce mismatch'
        if self.balances.get(sender, 0) < amount:
            return False, 'insufficient funds'
        self.balances[sender] -= amount
        self.balances[recipient] = self.balances.get(recipient, 0) + amount
        self.nonces[sender] = p['nonce'] + 1
        self.height += 1
        self.history.append(hashlib.sha256(canonical(tx)).hexdigest())
        return True, 'executed'

    def digest(self):
        return hashlib.sha256(canonical({'height': self.height, 'balances': self.balances, 'nonces': self.nonces, 'history': self.history})).hexdigest()


def worker(worker_id, balances, inbound, outbound):
    ledger = Ledger(balances)
    while True:
        command = inbound.get()
        if command['op'] == 'stop':
            return
        if command['op'] == 'apply':
            ok, message = ledger.apply(command['tx'])
            outbound.put({'worker': worker_id, 'ok': ok, 'message': message, 'height': ledger.height, 'digest': ledger.digest()})
        if command['op'] == 'state':
            outbound.put({'worker': worker_id, 'height': ledger.height, 'digest': ledger.digest(), 'balances': ledger.balances})


def run_demo():
    sender_priv, sender_pub, sender = new_identity()
    _, _, recipient = new_identity()
    balances = {sender: 1000, recipient: 0}
    ctx = mp.get_context('spawn')
    inbound = [ctx.Queue() for _ in range(4)]
    outbound = ctx.Queue()
    processes = [ctx.Process(target=worker, args=(i, balances, inbound[i], outbound)) for i in range(4)]
    for p in processes:
        p.start()
    try:
        tx = signed_transfer(sender_priv, sender_pub, recipient, 125, 0)
        for q in inbound:
            q.put({'op': 'apply', 'tx': tx})
        results = [outbound.get(timeout=15) for _ in processes]
        assert all(r['ok'] for r in results)
        assert len({r['digest'] for r in results}) == 1
        return {'independent_processes': 4, 'transfer_amount': 125, 'height': 1, 'matching_state_digests': 4, 'consensus': 'NOT IMPLEMENTED', 'finality': 'NOT IMPLEMENTED'}
    finally:
        for q in inbound:
            q.put({'op': 'stop'})
        for p in processes:
            p.join(timeout=5)
            if p.is_alive():
                p.terminate()
                p.join()


if __name__ == '__main__':
    print(json.dumps(run_demo(), indent=2))
