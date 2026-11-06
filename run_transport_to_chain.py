#!/usr/bin/env python3
"""Task 013: signed durable Task 012 transport into four-validator KASPYRA.
Local TCP only; validator consensus connectivity unchanged; no satellite hardware.
"""
import json
import hashlib
import os
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
import pathlib
import re
import select
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from task012.transport import Store, generate_key, sign, verify, flush, serve

ROOT = pathlib.Path(__file__).resolve().parents[1]
CHAIN = 'kaspyra-task013-local'
PORT = lambda i, offset: 26656 + 10 * i + offset
PROXY_PORT = lambda i, j: 28000 + 4 * i + j


def command(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()


def rpc(i, endpoint, **params):
    url = f'http://127.0.0.1:{PORT(i, 1)}/{endpoint}?{urllib.parse.urlencode(params)}'
    with urllib.request.urlopen(url, timeout=3) as response:
        data = json.load(response)
    if 'error' in data:
        raise RuntimeError(str(data['error']))
    return data['result']


def height(i):
    return int(rpc(i, 'status')['sync_info']['latest_block_height'])


def until(predicate, seconds=90, label='condition'):
    deadline = time.monotonic() + seconds
    last = None
    while time.monotonic() < deadline:
        try:
            result = predicate()
            if result:
                return result
        except Exception as exc:
            last = exc
        time.sleep(0.5)
    raise AssertionError(f'{label} timed out; last error: {last}')


def config_set(path, section, key, value):
    current = None
    found = False
    output = []
    for line in path.read_text().splitlines():
        match = re.match(r'^\s*\[([^]]+)\]\s*$', line)
        if match:
            current = match.group(1)
        if current == section and re.match(r'^\s*' + re.escape(key) + r'\s*=', line):
            line = f'{key} = {json.dumps(value)}'
            found = True
        output.append(line)
    if not found:
        raise AssertionError(f'missing {section}.{key} in {path}')
    path.write_text('\n'.join(output) + '\n')


def snapshot(indices=range(4)):
    common = min(height(i) for i in indices)
    if common < 2:
        raise AssertionError('insufficient finalized height')
    blocks = []
    for i in indices:
        if rpc(i, 'status')['node_info']['network'] != CHAIN:
            raise AssertionError(f'wrong chain ID on node {i}')
        block = rpc(i, 'block', height=common)
        blocks.append((block['block_id']['hash'], block['block']['header']['app_hash']))
    if len(set(blocks)) != 1:
        raise AssertionError(f'canonical disagreement at {common}: {blocks}')
    return {'height': common, 'block_id': blocks[0][0], 'app_hash': blocks[0][1]}


def stop(process):
    if process is None or process.poll() is not None:
        raise AssertionError('process not running when stop requested')
    process.terminate()
    try:
        process.wait(timeout=12)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


class LinkProxy:
    """One explicitly controlled directed TCP path from validator i to validator j."""
    def __init__(self, i, j):
        self.i, self.j = i, j
        self.allowed = True
        self.closed = threading.Event()
        self.lock = threading.Lock()
        self.connections = []
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(('127.0.0.1', PROXY_PORT(i, j)))
        self.listener.listen(16)
        self.listener.settimeout(0.5)
        self.thread = threading.Thread(target=self.accept_loop, daemon=True)
        self.thread.start()

    def accept_loop(self):
        while not self.closed.is_set():
            try:
                client, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            if not self.allowed:
                client.close()
                continue
            try:
                upstream = socket.create_connection(('127.0.0.1', PORT(self.j, 0)), timeout=3)
                client.setblocking(False)
                upstream.setblocking(False)
                with self.lock:
                    self.connections.append((client, upstream))
                threading.Thread(target=self.pipe, args=(client, upstream), daemon=True).start()
            except OSError:
                client.close()

    def pipe(self, a, b):
        try:
            while not self.closed.is_set() and self.allowed:
                readable, _, _ = select.select([a, b], [], [], 0.5)
                for source in readable:
                    try:
                        data = source.recv(65536)
                    except (OSError, BlockingIOError):
                        return
                    if not data:
                        return
                    target = b if source is a else a
                    target.setblocking(True)
                    try:
                        target.sendall(data)
                    finally:
                        target.setblocking(False)
        except OSError:
            pass
        finally:
            with self.lock:
                if (a, b) in self.connections:
                    self.connections.remove((a, b))
            for sock in (a, b):
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                sock.close()

    def set_allowed(self, value):
        self.allowed = value
        if not value:
            with self.lock:
                pairs = list(self.connections)
            for pair in pairs:
                for sock in pair:
                    try:
                        sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    sock.close()

    def close(self):
        self.closed.set()
        self.set_allowed(False)
        self.listener.close()
        self.thread.join(timeout=2)


def peer_ids(i):
    return {p['node_info']['id'] for p in rpc(i, 'net_info')['peers']}


def main():
    for executable in ('go', 'cometbft'):
        if not shutil.which(executable):
            raise RuntimeError(f'{executable} executable required')
    source = ROOT / 'task008c'
    if not (source / 'go.mod').exists():
        raise RuntimeError(f'missing {source / "go.mod"}')
    report = {'task': '013', 'phase': 'A', 'result': 'FAIL', 'experiments': {}}
    result_path = ROOT / 'task013-result.json'
    result_path.write_text(json.dumps(report, indent=2) + '\n')
    with tempfile.TemporaryDirectory(prefix='kaspyra-task013-') as temp:
        tmp = pathlib.Path(temp)
        binary = tmp / 'kaspyra-abci'
        subprocess.run(['go', 'build', '-o', str(binary), '.'], cwd=source, check=True)
        nodes, apps, consensus, logs, proxies = [], [None]*4, [None]*4, [], []
        try:
            for i in range(4):
                home = tmp / f'node{i}'
                home.mkdir()
                command('cometbft', 'init', 'validator', '--home', str(home))
                key = json.loads((home / 'config/priv_validator_key.json').read_text())
                node_id = command('cometbft', 'show-node-id', '--home', str(home))
                nodes.append((home, key, node_id))
            genesis = json.loads((nodes[0][0] / 'config/genesis.json').read_text())
            genesis['chain_id'] = CHAIN
            genesis['validators'] = [
                {'address': key['address'], 'pub_key': key['pub_key'], 'power': '10', 'name': f'kaspyra-{i}'}
                for i, (_, key, _) in enumerate(nodes)
            ]
            genesis['app_hash'] = ''
            sender = Ed25519PrivateKey.generate()
            receiver = Ed25519PrivateKey.generate()
            pub = sender.public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
            rpub = receiver.public_key().public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
            src = hashlib.sha256(pub).hexdigest()[:40]
            dst = hashlib.sha256(rpub).hexdigest()[:40]
            balances = {src: 1000, dst: 0}
            for i, (home, _, _) in enumerate(nodes):
                (home / 'config/genesis.json').write_text(json.dumps(genesis, indent=2) + '\n')
                (home / 'balances.json').write_text(json.dumps(balances) + '\n')
                conf = home / 'config/config.toml'
                config_set(conf, 'p2p', 'laddr', f'tcp://127.0.0.1:{PORT(i,0)}')
                config_set(conf, 'rpc', 'laddr', f'tcp://127.0.0.1:{PORT(i,1)}')
                config_set(conf, None, 'proxy_app', f'tcp://127.0.0.1:{PORT(i,2)}')
                peers = ','.join(f'{nid}@127.0.0.1:{PROXY_PORT(i,j)}' for j,(_,_,nid) in enumerate(nodes) if i != j)
                config_set(conf, 'p2p', 'persistent_peers', peers)
                config_set(conf, 'p2p', 'pex', False)
                config_set(conf, 'p2p', 'addr_book_strict', False)
                config_set(conf, 'p2p', 'allow_duplicate_ip', True)
                config_set(conf, 'consensus', 'timeout_commit', '1s')
                config_set(conf, 'consensus', 'create_empty_blocks', True)
                config_set(conf, 'consensus', 'create_empty_blocks_interval', '0s')

            for i in range(4):
                for j in range(4):
                    if i != j:
                        proxies.append(LinkProxy(i, j))

            def start_app(i, suffix=''):
                home = nodes[i][0]
                log = open(tmp / f'app{i}{suffix}.log', 'w')
                logs.append(log)
                apps[i] = subprocess.Popen([
                    str(binary), '-listen', f'tcp://127.0.0.1:{PORT(i,2)}',
                    '-state', str(home / 'data/appstate.json'), '-chain', CHAIN,
                    '-balances', str(home / 'balances.json')], stdout=log, stderr=subprocess.STDOUT)

            def start_node(i, suffix=''):
                log = open(tmp / f'consensus{i}{suffix}.log', 'w')
                logs.append(log)
                consensus[i] = subprocess.Popen(['cometbft', 'node', '--home', str(nodes[i][0])], stdout=log, stderr=subprocess.STDOUT)

            for i in range(4):
                start_app(i)
            time.sleep(2)
            for i in range(4):
                start_node(i)
            until(lambda: all(height(i) >= 4 for i in range(4)), 120, 'four-node startup')
            until(lambda: all(len(peer_ids(i)) >= 3 for i in range(4)), 60, 'baseline peer connectivity')
            baseline = snapshot()
            print('BASELINE', json.dumps(baseline), flush=True)

            # Task 012 authenticates and durably transports transaction bytes.
            # This is a client gateway; CometBFT P2P remains direct and unmodified.
            def make_tx(nonce, amount):
                payload = {'chain_id': CHAIN, 'from': src, 'to': dst, 'amount': amount, 'nonce': nonce}
                signed_bytes = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode()
                tx = {**payload, 'public_key': pub.hex(), 'signature': sender.sign(signed_bytes).hex()}
                return json.dumps(tx, separators=(',', ':')).encode()

            key_path = tmp / 'relay.key'
            trusted_pub = generate_key(key_path)
            sender_db = str(tmp / 'sender.sqlite')
            receiver_db = str(tmp / 'receiver.sqlite')
            gateway = Store(receiver_db)
            sender_store = Store(sender_db)
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', 0))
                transport_port = probe.getsockname()[1]
            first = make_tx(0, 125)
            first_env = sign(key_path, first, ttl=120)
            sender_store.queue(first_env)
            sender_store.queue(first_env)
            if len(sender_store.pending()) != 1:
                raise AssertionError('durable outbox failed to suppress duplicate envelope')
            before = snapshot()
            # No transport listener: the network remains alive while the signed
            # transaction is queued. Failed flush must preserve the outbox.
            offline = flush(sender_db, port=transport_port)
            if len(offline) != 1 or offline[0][1] != 'pending':
                raise AssertionError(f'expected pending while gateway offline: {offline}')
            if len(Store(sender_db).pending()) != 1:
                raise AssertionError('queued transaction lost during outage')
            until(lambda: min(height(i) for i in range(4)) > before['height'], 25,
                  'consensus progress while transaction gateway offline')
            print('TRANSPORT_OUTAGE_QUEUE PASS', flush=True)
            report['experiments']['transport_outage_queue'] = {'result': 'PASS'}

            listener = threading.Thread(target=serve, args=(receiver_db, {trusted_pub},
                                      '127.0.0.1', transport_port, 2), daemon=True)
            listener.start()
            delivered = until(lambda: [r for r in flush(sender_db, port=transport_port)
                                       if r[1] in ('accepted', 'duplicate')], 20,
                              'signed transport delivery')
            if delivered[0][1] != 'accepted':
                raise AssertionError(f'expected authenticated acceptance: {delivered}')
            # Resend the identical envelope: durable receiver must suppress it.
            with socket.create_connection(('127.0.0.1', transport_port), timeout=3) as sock:
                from task012.transport import send_frame, recv_frame
                send_frame(sock, first_env)
                duplicate_ack = recv_frame(sock)
            listener.join(timeout=5)
            if listener.is_alive() or duplicate_ack.get('status') != 'duplicate':
                raise AssertionError(f'gateway did not suppress duplicate: {duplicate_ack}')
            if Store(receiver_db).db.execute('SELECT COUNT(*) FROM inbox').fetchone()[0] != 1:
                raise AssertionError('duplicate receiver inbox entry')
            print('SIGNED_TRANSPORT_DELIVERY PASS', flush=True)
            report['experiments']['signed_transport_delivery'] = {'result': 'PASS'}

            # Gateway processing: only a verified, persisted inbox payload is
            # submitted to KASPYRA RPC. Transport ACK is not a chain receipt.
            raw = Store(receiver_db).db.execute('SELECT payload FROM inbox').fetchone()[0]
            if raw != verify(first_env, {trusted_pub}):
                raise AssertionError('receiver payload mismatch')
            response = rpc(0, 'broadcast_tx_sync', tx='0x' + raw.hex())
            if int(response['code']) != 0:
                raise AssertionError(f'RPC rejected authenticated transaction: {response}')
            txhash = response['hash']
            txinfo = until(lambda: rpc(0, 'tx', hash='0x' + txhash, prove='false'),
                           90, 'transaction inclusion')
            if int(txinfo['tx_result']['code']) != 0:
                raise AssertionError(f'committed transaction failed: {txinfo}')
            txheight = int(txinfo['height'])
            until(lambda: all(height(i) >= txheight + 2 for i in range(4)),
                  90, 'four validator convergence')
            included = snapshot()
            for home, _, _ in nodes:
                accounts = json.loads((home / 'data/appstate.json').read_text())['accounts']
                if accounts[src] != {'balance': 875, 'nonce': 1} or accounts[dst]['balance'] != 125:
                    raise AssertionError(f'incorrect finalized account state: {accounts}')
            print('TRANSPORT_TO_FINALITY PASS', flush=True)
            report['experiments']['transport_to_finality'] = {
                'result': 'PASS', 'tx_hash': txhash, 'included_height': txheight,
                'converged': included, 'balances': {'sender': 875, 'receiver': 125}}

            # An expired signed envelope cannot enter the durable receiver inbox.
            expired = sign(key_path, make_tx(1, 20), ttl=1, now=int(time.time()) - 3)
            try:
                Store(receiver_db).accept(expired, {trusted_pub})
            except ValueError:
                pass
            else:
                raise AssertionError('expired envelope accepted')
            if Store(receiver_db).db.execute('SELECT COUNT(*) FROM inbox').fetchone()[0] != 1:
                raise AssertionError('expired envelope persisted')
            print('EXPIRED_ENVELOPE_REJECTED PASS', flush=True)
            report['experiments']['expired_envelope_rejected'] = {'result': 'PASS'}

            # Restarted stores must preserve outbox ACK and inbox deduplication.
            if Store(sender_db).pending():
                raise AssertionError('delivered outbox reappeared after restart')
            if Store(receiver_db).accept(first_env, {trusted_pub}) != 'duplicate':
                raise AssertionError('inbox deduplication did not survive restart')
            print('PERSISTENT_RESTART_STATE PASS', flush=True)
            report['experiments']['persistent_restart_state'] = {'result': 'PASS'}
            report['result'] = 'PASS_PHASE_A'
        except Exception as exc:
            report['error'] = repr(exc)
            for log in logs:
                log.flush()
            for path in sorted(tmp.glob('*.log')):
                print(f'\n===== {path.name} (last 45 lines) =====', file=sys.stderr)
                print('\n'.join(path.read_text(errors='replace').splitlines()[-45:]), file=sys.stderr)
            raise
        finally:
            result_path.write_text(json.dumps(report, indent=2) + '\n')
            print(json.dumps(report, indent=2), flush=True)
            for p in consensus + apps:
                if p is not None and p.poll() is None:
                    p.terminate()
            for p in consensus + apps:
                if p is not None and p.poll() is None:
                    try:
                        p.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        p.kill()
            for link in proxies:
                link.close()
            for log in logs:
                log.close()


if __name__ == '__main__':
    main()
