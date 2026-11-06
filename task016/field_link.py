"""Task 016 field harness: authenticated delivery over a configured TCP link.
No claim of satellite path verification; use private tunnel for untrusted networks.
"""
import argparse
import hashlib
import json
import socket
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from task012.transport import Store, canonical, generate_key, recv_frame, send_frame, sign, verify


def transmit(db, host, port, timeout=5):
    store = Store(db)
    output = []
    for ident, env in store.pending():
        started = time.monotonic()
        wire = canonical(env)
        record = {'id': ident, 'bytes': len(wire), 'sha256': hashlib.sha256(wire).hexdigest()}
        try:
            with socket.create_connection((host, port), timeout=timeout) as sock:
                sock.settimeout(timeout)
                send_frame(sock, env)
                answer = recv_frame(sock)
            record['status'] = answer.get('status', 'invalid-response')
            if record['status'] in ('accepted', 'duplicate'):
                store.mark(ident)
        except (OSError, ConnectionError, TimeoutError, ValueError) as exc:
            record['status'] = 'pending'
            record['error'] = type(exc).__name__
        record['round_trip_ms'] = round((time.monotonic() - started) * 1000, 2)
        output.append(record)
    return output


def handle(conn, store, allowlist, rpc_url=None):
    started = time.monotonic()
    try:
        env = recv_frame(conn)
        payload = verify(env, allowlist)
        status = store.accept(env, allowlist)
        # Only a verified, persisted transaction can be submitted to the local RPC.
        # RPC failure does not undo inbox persistence; use inbox audit/retry separately.
        result = {'status': status, 'payload_sha256': hashlib.sha256(payload).hexdigest()}
        if rpc_url and status == 'accepted':
            url = rpc_url.rstrip('/') + '/broadcast_tx_sync?tx=0x' + payload.hex()
            try:
                with urllib.request.urlopen(url, timeout=5) as response:
                    rpc = json.load(response)
                result['rpc'] = rpc.get('result', {})
                if rpc.get('error') or result['rpc'].get('code', 0) != 0:
                    result['rpc_error'] = True
            except Exception as exc:
                result['rpc_error'] = type(exc).__name__
        result['processing_ms'] = round((time.monotonic() - started) * 1000, 2)
    except Exception as exc:
        result = {'status': 'rejected', 'reason': type(exc).__name__}
    send_frame(conn, result)
    return result


def listen(db, allowlist, host, port, rpc_url=None, max_connections=None):
    store = Store(db)
    count = 0
    with socket.socket() as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(16)
        print(json.dumps({'listening': f'{host}:{port}', 'mode': 'tcp-field-harness', 'satellite_verified': False}), flush=True)
        while max_connections is None or count < max_connections:
            conn, _ = server.accept()
            with conn:
                conn.settimeout(5)
                result = handle(conn, store, allowlist, rpc_url)
                print(json.dumps(result), flush=True)
            count += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='cmd', required=True)
    g = subs.add_parser('keygen'); g.add_argument('key')
    q = subs.add_parser('queue'); q.add_argument('db'); q.add_argument('key'); q.add_argument('payload_file'); q.add_argument('--ttl', type=int, default=300)
    l = subs.add_parser('listen'); l.add_argument('db'); l.add_argument('allowlist'); l.add_argument('--host', default='127.0.0.1'); l.add_argument('--port', type=int, default=18716); l.add_argument('--max-connections', type=int); l.add_argument('--rpc-url')
    t = subs.add_parser('transmit'); t.add_argument('db'); t.add_argument('--host', default='127.0.0.1'); t.add_argument('--port', type=int, default=18716); t.add_argument('--timeout', type=float, default=5)
    args = parser.parse_args()
    if args.cmd == 'keygen':
        print(generate_key(args.key))
    elif args.cmd == 'queue':
        env = sign(args.key, Path(args.payload_file).read_bytes(), args.ttl)
        Store(args.db).queue(env)
        print(json.dumps({'queued': env['body']['id']}))
    elif args.cmd == 'listen':
        listen(args.db, set(Path(args.allowlist).read_text().splitlines()), args.host, args.port, args.rpc_url, args.max_connections)
    elif args.cmd == 'transmit':
        print(json.dumps({'attempts': transmit(args.db, args.host, args.port, args.timeout), 'satellite_verified': False}, indent=2))

if __name__ == '__main__':
    main()
