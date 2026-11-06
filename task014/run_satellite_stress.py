#!/usr/bin/env python3
"""KASPYRA Task 014: validator P2P satellite-like impairment stress.

Experimental local-only integration. No Byzantine or satellite-link claim.
"""
import json
import random
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
CHAIN = 'kaspyra-task014-local'
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
        self.delay_seconds = 0.0
        self.jitter_seconds = 0.0
        self.bandwidth_bytes_per_second = 0
        self.loss_probability = 0.0
        self.rng = random.Random(i * 101 + j)
        self.bytes_forwarded = 0
        self.chunks_forwarded = 0
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
                    # Apply delay to actual validator TCP traffic, not to RPC/client submission.
                    # TCP loss is modeled as connection disruption, never silent
                    # byte deletion (which would corrupt the stream protocol).
                    if self.loss_probability and self.rng.random() < self.loss_probability:
                        return
                    delay = self.delay_seconds
                    if self.jitter_seconds:
                        delay += self.rng.uniform(0, self.jitter_seconds)
                    if self.bandwidth_bytes_per_second:
                        delay += len(data) / self.bandwidth_bytes_per_second
                    if delay:
                        time.sleep(delay)
                    target.setblocking(True)
                    try:
                        target.sendall(data)
                        with self.lock:
                            self.bytes_forwarded += len(data)
                            self.chunks_forwarded += 1
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
    report = {'task': '014', 'phase': 'stress', 'result': 'FAIL', 'experiments': {}, 'scope': 'local TCP proxy latency; no real satellite link'}
    result_path = ROOT / 'task014-result.json'
    result_path.write_text(json.dumps(report, indent=2) + '\n')
    with tempfile.TemporaryDirectory(prefix='kaspyra-task014-') as temp:
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
            balances = {'a'*40: 1000, 'b'*40: 0}
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

            # Each proxy forwards both directions of a TCP stream. Delays are
            # applied per received chunk; these are NOT calibrated RTT values.
            def metrics():
                return {'total_bytes': sum(p.bytes_forwarded for p in proxies),
                        'total_chunks': sum(p.chunks_forwarded for p in proxies),
                        'min_height': min(height(i) for i in range(4)),
                        'max_height': max(height(i) for i in range(4))}

            scenarios = [
                ('delay_500ms', dict(delay_seconds=0.5), 140),
                ('delay_1000ms', dict(delay_seconds=1.0), 180),
                ('jitter_100_700ms', dict(delay_seconds=0.1, jitter_seconds=0.6), 160),
                ('bandwidth_128kBps', dict(bandwidth_bytes_per_second=128_000), 120),
                ('connection_disruption_1pct', dict(loss_probability=0.01), 180),
            ]
            for name, settings, deadline in scenarios:
                for link in proxies:
                    link.delay_seconds = 0.0
                    link.jitter_seconds = 0.0
                    link.bandwidth_bytes_per_second = 0
                    link.loss_probability = 0.0
                    for key, value in settings.items():
                        setattr(link, key, value)
                before = metrics()
                t0 = time.monotonic()
                target = before['max_height'] + 2
                try:
                    until(lambda: min(height(i) for i in range(4)) >= target,
                          deadline, name + ' progress')
                    outcome = 'PASS'
                except AssertionError:
                    outcome = 'STALL'
                elapsed = round(time.monotonic() - t0, 3)
                after = metrics()
                report['experiments'][name] = {
                    'result': outcome, 'settings': settings,
                    'seconds_observed': elapsed, 'target_height': target,
                    'before': before, 'after': after}
                print(name.upper(), outcome, json.dumps(report['experiments'][name]), flush=True)
                # A stall is a measured outcome, not automatically a harness failure.
                # Restore healthy connectivity before the next scenario.
                for link in proxies:
                    link.delay_seconds = 0.0
                    link.jitter_seconds = 0.0
                    link.bandwidth_bytes_per_second = 0
                    link.loss_probability = 0.0
                until(lambda: all(len(peer_ids(i)) >= 3 for i in range(4)),
                      90, 'reconnect after ' + name)
                until(lambda: min(height(i) for i in range(4)) >= target,
                      120, 'recover progress after ' + name)
                snapshot()

            # Restore undelayed links, then partition validators 2 vs 2.
            for link in proxies:
                link.delay_seconds = 0
                link.jitter_seconds = 0
                link.bandwidth_bytes_per_second = 0
                link.loss_probability = 0
            until(lambda: all(len(peer_ids(i)) >= 3 for i in range(4)), 45,
                  'all peers connected before partition')
            groups = ({0, 1}, {2, 3})
            for link in proxies:
                if (link.i in groups[0]) != (link.j in groups[0]):
                    link.set_allowed(False)
            def isolated():
                peers = {i: peer_ids(i) for i in range(4)}
                for i in range(4):
                    own = groups[0] if i in groups[0] else groups[1]
                    other_ids = {nodes[j][2] for j in range(4) if j not in own}
                    if peers[i] & other_ids:
                        return False
                    if nodes[next(j for j in own if j != i)][2] not in peers[i]:
                        return False
                return True
            until(isolated, 45, 'verified 2-2 isolation')
            time.sleep(4)
            before = [height(i) for i in range(4)]
            time.sleep(12)
            after = [height(i) for i in range(4)]
            if before != after:
                raise AssertionError(f'chain advanced without quorum: {before} -> {after}')
            if any(p.poll() is not None for p in apps + consensus):
                raise AssertionError('process exited during outage')
            report['experiments']['two_two_outage'] = {
                'result': 'PASS', 'isolated': True, 'heights_before': before,
                'heights_after': after, 'observation_seconds': 12}
            print('TWO_TWO_OUTAGE PASS', flush=True)

            for link in proxies:
                link.set_allowed(True)
            until(lambda: all(len(peer_ids(i)) >= 3 for i in range(4)),
                  90, 'P2P reconnection')
            target = max(after) + 3
            until(lambda: min(height(i) for i in range(4)) >= target,
                  120, 'finality after outage')
            restored = snapshot()
            report['experiments']['recovery'] = {
                'result': 'PASS', 'converged': restored, 'metrics': metrics()}
            print('RECOVERY PASS', json.dumps(restored), flush=True)
            report['result'] = 'PASS_STRESS_COMPLETED' if all(v.get('result') == 'PASS' for k,v in report['experiments'].items() if k not in ('two_two_outage','recovery')) else 'PASS_WITH_MEASURED_STALLS'
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
