#!/usr/bin/env python3
"""KASPYRA Task 010: delayed and disrupted remote transaction submission.

Real four-validator CometBFT network; controlled client-to-RPC delivery only.
No physical satellite link or validator P2P latency is simulated here.
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

ROOT = pathlib.Path(__file__).resolve().parents[1]
CHAIN = 'kaspyra-task010-local'
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
    report = {'task': '010', 'phase': 'A', 'result': 'FAIL', 'experiments': {}}
    result_path = ROOT / 'task010-result.json'
    result_path.write_text(json.dumps(report, indent=2) + '\n')
    with tempfile.TemporaryDirectory(prefix='kaspyra-task010-') as temp:
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

            # The relay models the remote client/ground-station boundary. Validators
            # remain fully connected throughout; no consensus timing is altered.
            def make_tx(nonce, amount):
                payload = {'chain_id': CHAIN, 'from': src, 'to': dst, 'amount': amount, 'nonce': nonce}
                signed_bytes = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode()
                tx = {**payload, 'public_key': pub.hex(), 'signature': sender.sign(signed_bytes).hex()}
                return json.dumps(tx, separators=(',', ':')).encode()

            class Relay:
                def __init__(self):
                    self.online = True
                    self.queue = {}
                    self.sent = set()
                    self.events = []

                def enqueue(self, raw, delay=0, ttl=30):
                    digest = hashlib.sha256(raw).hexdigest()
                    if digest in self.queue or digest in self.sent:
                        self.events.append({'event': 'duplicate_suppressed', 'tx': digest})
                        return False
                    now = time.monotonic()
                    self.queue[digest] = (raw, now + delay, now + ttl)
                    return True

                def flush(self):
                    now = time.monotonic()
                    for digest, (raw, ready, expiry) in list(self.queue.items()):
                        if now >= expiry:
                            self.queue.pop(digest)
                            self.events.append({'event': 'expired', 'tx': digest})
                        elif self.online and now >= ready:
                            response = rpc(0, 'broadcast_tx_sync', tx='0x' + raw.hex())
                            if int(response['code']) != 0:
                                raise AssertionError(f'network rejected queued transfer: {response}')
                            self.queue.pop(digest)
                            self.sent.add(digest)
                            self.events.append({'event': 'submitted', 'tx': digest, 'hash': response['hash']})
                def submissions(self):
                    return [e for e in self.events if e['event'] == 'submitted']

            relay = Relay()
            first = make_tx(0, 125)
            relay.online = False
            if not relay.enqueue(first, delay=2, ttl=30):
                raise AssertionError('first enqueue failed')
            if relay.enqueue(first, delay=2, ttl=30):
                raise AssertionError('duplicate was accepted')
            before = snapshot()
            time.sleep(3)
            relay.flush()
            if relay.submissions():
                raise AssertionError('transaction submitted during simulated uplink outage')
            if min(height(i) for i in range(4)) <= before['height']:
                raise AssertionError('validators stopped during client-only outage')
            relay.online = True
            start_delivery = time.monotonic()
            relay.flush()
            submissions = relay.submissions()
            if len(submissions) != 1:
                raise AssertionError(f'expected exactly one relay submission: {submissions}')
            txhash = submissions[0]['hash']
            txinfo = until(lambda: rpc(0, 'tx', hash='0x' + txhash, prove='false'), 90, 'transaction inclusion')
            if int(txinfo['tx_result']['code']) != 0:
                raise AssertionError(f'failed finalized transfer: {txinfo}')
            txheight = int(txinfo['height'])
            until(lambda: all(height(i) >= txheight + 2 for i in range(4)), 90, 'post-transfer agreement')
            included = snapshot()
            for home, _, _ in nodes:
                accounts = json.loads((home / 'data/appstate.json').read_text())['accounts']
                if accounts[src] != {'balance': 875, 'nonce': 1} or accounts[dst]['balance'] != 125:
                    raise AssertionError(f'invalid committed account state: {accounts}')
            report['experiments']['delayed_outage_delivery'] = {
                'result': 'PASS', 'artificial_delay_seconds': 2,
                'uplink_outage_seconds': 3, 'included_height': txheight,
                'delivery_to_inclusion_seconds': round(time.monotonic()-start_delivery, 3),
                'converged': included}
            print('DELAYED_OUTAGE_DELIVERY PASS', flush=True)

            # Expired transactions must never reach RPC, even after reconnect.
            relay.online = False
            expired = make_tx(1, 20)
            relay.enqueue(expired, delay=0, ttl=1)
            time.sleep(1.3)
            relay.online = True
            relay.flush()
            if relay.queue or len(relay.submissions()) != 1:
                raise AssertionError('expired transfer was submitted')
            report['experiments']['expiry'] = {'result': 'PASS', 'expired_without_submission': True}
            print('EXPIRY PASS', flush=True)

            # The relay must suppress repeats both before and after submission.
            if relay.enqueue(first):
                raise AssertionError('already-sent transaction re-enqueued')
            if len(relay.submissions()) != 1:
                raise AssertionError('unexpected additional relay submission')
            report['experiments']['duplicate_suppression'] = {'result': 'PASS', 'network_submissions': 1}
            print('DUPLICATE_SUPPRESSION PASS', flush=True)

            # A fresh transaction with the next nonce remains valid after outage.
            second = make_tx(1, 25)
            relay.enqueue(second, delay=0, ttl=30)
            relay.flush()
            second_hash = relay.submissions()[-1]['hash']
            second_info = until(lambda: rpc(0, 'tx', hash='0x' + second_hash, prove='false'), 90, 'second inclusion')
            if int(second_info['tx_result']['code']) != 0:
                raise AssertionError(f'second transfer failed: {second_info}')
            second_height = int(second_info['height'])
            until(lambda: all(height(i) >= second_height + 2 for i in range(4)), 90, 'second transfer convergence')
            final = snapshot()
            for home, _, _ in nodes:
                accounts = json.loads((home / 'data/appstate.json').read_text())['accounts']
                if accounts[src] != {'balance': 850, 'nonce': 2} or accounts[dst]['balance'] != 150:
                    raise AssertionError('wrong final balances or nonce')
            report['experiments']['post_outage_transfer'] = {'result': 'PASS', 'height': second_height, 'converged': final}
            print('POST_OUTAGE_TRANSFER PASS', flush=True)
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
