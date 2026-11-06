"""Experimental authenticated, durable, store-and-forward TCP message transport.
NOT a satellite modem, validator P2P adapter, or production security boundary.
"""
import argparse
import base64
import hashlib
import json
import socket
import sqlite3
import struct
import time
import uuid
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization

MAX_FRAME = 65536
MAX_PAYLOAD = 16384

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()

def generate_key(path):
    key = Ed25519PrivateKey.generate()
    raw = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    Path(path).write_bytes(raw)
    Path(path).chmod(0o600)
    return key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()

def sign(key_path, payload, ttl=300, now=None):
    if len(payload) > MAX_PAYLOAD or ttl <= 0 or ttl > 86400:
        raise ValueError('payload or TTL outside limits')
    key = Ed25519PrivateKey.from_private_bytes(Path(key_path).read_bytes())
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    now = int(time.time() if now is None else now)
    body = {'v': 1, 'id': str(uuid.uuid4()), 'sender': pub, 'issued': now, 'expires': now + ttl,
            'payload': base64.b64encode(payload).decode()}
    return {'body': body, 'signature': key.sign(canonical(body)).hex()}

def verify(envelope, allowlist, now=None):
    body = envelope['body']
    if set(body) != {'v','id','sender','issued','expires','payload'} or body['v'] != 1:
        raise ValueError('invalid schema')
    if body['sender'] not in allowlist:
        raise ValueError('untrusted sender')
    now = int(time.time() if now is None else now)
    if not isinstance(body['issued'], int) or not isinstance(body['expires'], int) or not body['issued'] - 60 <= now < body['expires'] or body['expires'] - body['issued'] > 86400:
        raise ValueError('expired or invalid timestamp')
    payload = base64.b64decode(body['payload'], validate=True)
    if len(payload) > MAX_PAYLOAD:
        raise ValueError('oversized payload')
    Ed25519PublicKey.from_public_bytes(bytes.fromhex(body['sender'])).verify(bytes.fromhex(envelope['signature']), canonical(body))
    return payload

class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS inbox (id TEXT PRIMARY KEY, sender TEXT, received INTEGER, payload BLOB)')
        self.db.execute('CREATE TABLE IF NOT EXISTS outbox (id TEXT PRIMARY KEY, envelope TEXT, delivered INTEGER DEFAULT 0)')
        self.db.commit()
    def accept(self, env, allowlist, now=None):
        payload = verify(env, allowlist, now)
        body = env['body']
        with self.db:
            result = self.db.execute('INSERT OR IGNORE INTO inbox VALUES (?,?,?,?)', (body['id'],body['sender'],int(time.time()),payload))
        return 'accepted' if result.rowcount else 'duplicate'
    def queue(self, env):
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO outbox(id,envelope) VALUES (?,?)', (env['body']['id'], canonical(env).decode()))
    def pending(self):
        return [(i,json.loads(e)) for i,e in self.db.execute('SELECT id,envelope FROM outbox WHERE delivered=0 ORDER BY rowid')]
    def mark(self, id):
        with self.db:
            self.db.execute('UPDATE outbox SET delivered=1 WHERE id=?', (id,))

def send_frame(sock, obj):
    raw = canonical(obj)
    if len(raw) > MAX_FRAME:
        raise ValueError('frame too large')
    sock.sendall(struct.pack('!I', len(raw)) + raw)

def recv_exact(sock, n):
    chunks = bytearray()
    while len(chunks) < n:
        data = sock.recv(n-len(chunks))
        if not data:
            raise ConnectionError('truncated frame')
        chunks.extend(data)
    return bytes(chunks)

def recv_frame(sock):
    n = struct.unpack('!I', recv_exact(sock, 4))[0]
    if n > MAX_FRAME:
        raise ValueError('frame too large')
    return json.loads(recv_exact(sock, n))

def serve(db, allowlist, host='127.0.0.1', port=18712, stop_after=None):
    store = Store(db)
    with socket.socket() as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host,port))
        server.listen(16)
        count = 0
        while stop_after is None or count < stop_after:
            conn,_ = server.accept()
            with conn:
                conn.settimeout(5)
                try:
                    status = store.accept(recv_frame(conn), allowlist)
                    send_frame(conn, {'status':status})
                except Exception as exc:
                    send_frame(conn, {'status':'rejected', 'reason':type(exc).__name__})
            count += 1

def flush(db, host='127.0.0.1', port=18712):
    store = Store(db)
    results = []
    for id,env in store.pending():
        try:
            with socket.create_connection((host,port),timeout=2) as sock:
                sock.settimeout(2)
                send_frame(sock,env)
                response = recv_frame(sock)
            if response.get('status') in ('accepted','duplicate'):
                store.mark(id)
            results.append((id,response['status']))
        except (OSError,ConnectionError,TimeoutError):
            results.append((id,'pending'))
    return results

def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest='cmd', required=True)
    g=sub.add_parser('keygen'); g.add_argument('path')
    s=sub.add_parser('queue'); s.add_argument('db'); s.add_argument('key'); s.add_argument('payload'); s.add_argument('--ttl',type=int,default=300)
    r=sub.add_parser('receive'); r.add_argument('db'); r.add_argument('allowlist'); r.add_argument('--host',default='127.0.0.1'); r.add_argument('--port',type=int,default=18712)
    f=sub.add_parser('flush'); f.add_argument('db'); f.add_argument('--host',default='127.0.0.1'); f.add_argument('--port',type=int,default=18712)
    a=p.parse_args()
    if a.cmd=='keygen': print(generate_key(a.path))
    if a.cmd=='queue':
        env=sign(a.key,a.payload.encode(),a.ttl); Store(a.db).queue(env); print(env['body']['id'])
    if a.cmd=='receive': serve(a.db,set(Path(a.allowlist).read_text().splitlines()),a.host,a.port)
    if a.cmd=='flush': print(json.dumps(flush(a.db,a.host,a.port)))

if __name__=='__main__': main()
