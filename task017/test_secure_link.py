import os
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from secure_link import contexts, serve, client


def openssl(*args, cwd):
    subprocess.run(['openssl', *args], cwd=cwd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0))
        return s.getsockname()[1]

class SecureLinkTests(unittest.TestCase):
    def test_contexts_require_peer_auth(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            openssl('req','-x509','-newkey','rsa:2048','-nodes','-keyout','ca.key','-out','ca.pem','-days','1','-subj','/CN=KASPYRA Test CA',cwd=d)
            openssl('req','-newkey','rsa:2048','-nodes','-keyout','server.key','-out','server.csr','-subj','/CN=localhost',cwd=d)
            (p/'ext.cnf').write_text('subjectAltName=DNS:localhost\nextendedKeyUsage=serverAuth,clientAuth\n')
            openssl('x509','-req','-in','server.csr','-CA','ca.pem','-CAkey','ca.key','-CAcreateserial','-out','server.pem','-days','1','-extfile','ext.cnf',cwd=d)
            s=contexts(str(p/'ca.pem'),str(p/'server.pem'),str(p/'server.key'),True)
            c=contexts(str(p/'ca.pem'),str(p/'server.pem'),str(p/'server.key'))
            self.assertEqual(s.verify_mode,ssl.CERT_REQUIRED)
            self.assertTrue(c.check_hostname)
            self.assertEqual(c.verify_mode,ssl.CERT_REQUIRED)
            self.assertGreaterEqual(s.minimum_version,ssl.TLSVersion.TLSv1_2)

    def test_reject_non_loopback_upstream(self):
        with self.assertRaises(ValueError):
            serve('127.0.0.1',0,'192.0.2.1',1234,'missing','missing','missing',1)

if __name__=='__main__': unittest.main()
