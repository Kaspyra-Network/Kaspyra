import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from task012.transport import Store, generate_key, sign
from task016.field_link import handle, transmit

class FieldLinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.key = self.root/'sender.key'
        self.pub = generate_key(self.key)
        self.outbox = str(self.root/'out.db')
        self.inbox = str(self.root/'in.db')
        self.env = sign(self.key, b'KASPYRA test message')
        initial = Store(self.outbox); initial.queue(self.env); initial.db.close()

    def receiver(self, count=1):
        ready = threading.Event()
        port_box = []
        def run():
            with socket.socket() as server:
                server.bind(('127.0.0.1', 0)); server.listen(4)
                port_box.append(server.getsockname()[1]); ready.set()
                store = Store(self.inbox)
                for _ in range(count):
                    conn, _ = server.accept()
                    with conn:
                        conn.settimeout(3)
                        handle(conn, store, {self.pub})
                store.db.close()
        thread = threading.Thread(target=run, daemon=True)
        thread.start(); self.assertTrue(ready.wait(3))
        return port_box[0], thread

    def test_outage_reconnect_and_persistence(self):
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0)); unused = s.getsockname()[1]
        attempts = transmit(self.outbox, '127.0.0.1', unused, .2)
        self.assertEqual(attempts[0]['status'], 'pending')
        port, thread = self.receiver()
        attempts = transmit(self.outbox, '127.0.0.1', port)
        self.assertEqual(attempts[0]['status'], 'accepted')
        thread.join(3); self.assertFalse(thread.is_alive())
        self.assertEqual(Store(self.inbox).db.execute('SELECT COUNT(*) FROM inbox').fetchone()[0], 1)
        self.assertEqual(Store(self.outbox).pending(), [])
        self.assertEqual(transmit(self.outbox, '127.0.0.1', port), [])
        self.assertGreater(attempts[0]['bytes'], 0)

    def test_untrusted_sender_rejected(self):
        other = self.root/'other.key'; generate_key(other)
        port, thread = self.receiver()
        # replace allowlist in receiver by signing with an unrelated key
        store = Store(self.outbox)
        store.db.execute('DELETE FROM outbox'); store.db.commit()
        store.queue(sign(other, b'untrusted')); store.db.close()
        attempts = transmit(self.outbox, '127.0.0.1', port)
        self.assertEqual(attempts[0]['status'], 'rejected')
        self.assertEqual(len(Store(self.outbox).pending()), 1)
        thread.join(3)

    def test_expired_rejected(self):
        store = Store(self.outbox)
        store.db.execute('DELETE FROM outbox'); store.db.commit()
        store.queue(sign(self.key, b'old', ttl=1, now=1)); store.db.close()
        port, thread = self.receiver()
        attempts = transmit(self.outbox, '127.0.0.1', port)
        self.assertEqual(attempts[0]['status'], 'rejected')
        thread.join(3)

if __name__ == '__main__': unittest.main()
