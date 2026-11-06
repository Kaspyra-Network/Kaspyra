import tempfile
import threading
import time
import unittest
from pathlib import Path
from task012.transport import Store, generate_key, sign, verify, flush, serve

class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.key = self.root/'key'
        self.pub = generate_key(self.key)
        self.receiver = str(self.root/'receiver.db')
        self.sender = str(self.root/'sender.db')
    def test_sign_and_tamper(self):
        env=sign(self.key,b'hello')
        self.assertEqual(verify(env,{self.pub}),b'hello')
        env['body']['payload']='aGFja2Vk'
        with self.assertRaises(Exception): verify(env,{self.pub})
    def test_untrusted_and_expired(self):
        env=sign(self.key,b'x',now=100,ttl=10)
        with self.assertRaises(ValueError): verify(env,set(),now=101)
        with self.assertRaises(ValueError): verify(env,{self.pub},now=110)
    def test_duplicate_persists_restart(self):
        env=sign(self.key,b'hello')
        self.assertEqual(Store(self.receiver).accept(env,{self.pub}),'accepted')
        self.assertEqual(Store(self.receiver).accept(env,{self.pub}),'duplicate')
        self.assertEqual(Store(self.receiver).db.execute('SELECT count(*) FROM inbox').fetchone()[0],1)
    def test_outage_then_reconnect(self):
        env=sign(self.key,b'kaspyra-test')
        Store(self.sender).queue(env)
        with __import__('socket').socket() as probe:
            probe.bind(('127.0.0.1',0)); port=probe.getsockname()[1]
        self.assertEqual(flush(self.sender,port=port)[0][1],'pending')
        t=threading.Thread(target=serve,args=(self.receiver,{self.pub},'127.0.0.1',port,1),daemon=True)
        t.start()
        for _ in range(50):
            result=flush(self.sender,port=port)
            if result and result[0][1]=='accepted': break
            time.sleep(.02)
        self.assertEqual(result[0][1],'accepted')
        t.join(timeout=3)
        self.assertEqual(flush(self.sender,port=port),[])
        self.assertEqual(Store(self.receiver).db.execute('SELECT payload FROM inbox').fetchone()[0],b'kaspyra-test')

if __name__=='__main__': unittest.main()
