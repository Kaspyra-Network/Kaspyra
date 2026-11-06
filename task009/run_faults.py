#!/usr/bin/env python3
"""KASPYRA Task 009A: real CometBFT 4-validator process-failure experiments.

No network partition is claimed. This runner intentionally fails closed on missing
RPC, missing blocks, or inconsistent canonical block IDs/app hashes.
"""
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
CHAIN = 'kaspyra-task009a-local'
PORT = lambda i, offset: 26656 + 10*i + offset


def run(*args, **kw):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT, **kw).strip()


def rpc(i, endpoint, **params):
    url = f'http://127.0.0.1:{PORT(i,1)}/{endpoint}?{urllib.parse.urlencode(params)}'
    with urllib.request.urlopen(url, timeout=3) as response:
        obj = json.load(response)
    if 'error' in obj:
        raise RuntimeError(str(obj['error']))
    return obj['result']


def height(i):
    return int(rpc(i, 'status')['sync_info']['latest_block_height'])


def wait_for(fn, seconds=90, label='condition'):
    end = time.monotonic() + seconds
    last = None
    while time.monotonic() < end:
        try:
            value = fn()
            if value:
                return value
        except Exception as exc:
            last = exc
        time.sleep(0.5)
    raise AssertionError(f'{label} timed out; last error: {last}')


def set_toml(path, section, key, value):
    current = None
    found = False
    lines = []
    for line in path.read_text().splitlines():
        match = re.match(r'^\s*\[([^]]+)\]\s*$', line)
        if match:
            current = match.group(1)
        if current == section and re.match(r'^\s*'+re.escape(key)+r'\s*=', line):
            line = f'{key} = {json.dumps(value)}'
            found = True
        lines.append(line)
    if not found:
        raise AssertionError(f'missing config key {section}.{key} in {path}')
    path.write_text('\n'.join(lines)+'\n')


def snapshot(indices):
    """Compare canonical block IDs and application hashes at same height."""
    heights = [height(i) for i in indices]
    common = min(heights)
    if common < 2:
        raise AssertionError(f'insufficient block height: {heights}')
    ids = []
    hashes = []
    for i in indices:
        status = rpc(i, 'status')
        if status['node_info']['network'] != CHAIN:
            raise AssertionError(f'wrong chain at node {i}')
        block = rpc(i, 'block', height=common)
        ids.append(block['block_id']['hash'])
        hashes.append(block['block']['header']['app_hash'])
    if len(set(ids)) != 1 or len(set(hashes)) != 1:
        raise AssertionError(f'canonical mismatch at {common}: ids={ids}, apps={hashes}')
    return {'height': common, 'block_id': ids[0], 'app_hash': hashes[0]}


def stop(process):
    if process.poll() is not None:
        raise AssertionError(f'process already exited: {process.returncode}')
    process.terminate()
    try:
        process.wait(timeout=12)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def main():
    for name in ('go', 'cometbft'):
        if not shutil.which(name):
            raise RuntimeError(f'{name} executable not found')
    source = ROOT/'task008c'
    if not (source/'go.mod').exists():
        raise RuntimeError(f'missing {source}/go.mod')
    with tempfile.TemporaryDirectory(prefix='kaspyra-task009-') as directory:
        tmp = pathlib.Path(directory)
        binary = tmp/'kaspyra-abci'
        subprocess.run(['go', 'build', '-o', str(binary), '.'], cwd=source, check=True)
        nodes = []
        apps = []
        consensus = [None]*4
        logs = []
        results = {}
        try:
            for i in range(4):
                home = tmp/f'node{i}'
                home.mkdir()
                run('cometbft','init','validator','--home',str(home))
                key = json.loads((home/'config/priv_validator_key.json').read_text())
                node_id = run('cometbft','show-node-id','--home',str(home))
                nodes.append((home,key,node_id))
            genesis = json.loads((nodes[0][0]/'config/genesis.json').read_text())
            genesis['chain_id'] = CHAIN
            genesis['validators'] = [
                {'address': key['address'], 'pub_key': key['pub_key'], 'power':'10', 'name':f'kaspyra-{i}'}
                for i, (_,key,_) in enumerate(nodes)
            ]
            genesis['app_hash'] = ''
            # Deterministic fixture, not production keys or funds.
            balances = {'a'*40: 1000, 'b'*40: 0}
            for i, (home,_,_) in enumerate(nodes):
                (home/'config/genesis.json').write_text(json.dumps(genesis,indent=2)+'\n')
                (home/'balances.json').write_text(json.dumps(balances)+'\n')
                config = home/'config/config.toml'
                set_toml(config, 'p2p', 'laddr', f'tcp://127.0.0.1:{PORT(i,0)}')
                set_toml(config, 'rpc', 'laddr', f'tcp://127.0.0.1:{PORT(i,1)}')
                set_toml(config, None, 'proxy_app', f'tcp://127.0.0.1:{PORT(i,2)}')
                peers = ','.join(f'{nid}@127.0.0.1:{PORT(j,0)}' for j,(_,_,nid) in enumerate(nodes) if j!=i)
                set_toml(config,'p2p','persistent_peers',peers)
                set_toml(config,'p2p','addr_book_strict',False)
                set_toml(config,'p2p','allow_duplicate_ip',True)
                set_toml(config,'consensus','timeout_commit','1s')
                set_toml(config,'consensus','create_empty_blocks',True)
                set_toml(config,'consensus','create_empty_blocks_interval','0s')
                log = open(tmp/f'app{i}.log','w')
                logs.append(log)
                apps.append(subprocess.Popen([
                    str(binary),'-listen',f'tcp://127.0.0.1:{PORT(i,2)}',
                    '-state',str(home/'data/appstate.json'),'-chain',CHAIN,
                    '-balances',str(home/'balances.json')],stdout=log,stderr=subprocess.STDOUT))
            time.sleep(2)

            def start_node(i, suffix=''):
                home = nodes[i][0]
                log = open(tmp/f'consensus{i}{suffix}.log','w')
                logs.append(log)
                consensus[i] = subprocess.Popen(['cometbft','node','--home',str(home)],stdout=log,stderr=subprocess.STDOUT)

            for i in range(4):
                start_node(i)
            wait_for(lambda: all(height(i)>=4 for i in range(4)),120,'healthy four-node startup')
            baseline = snapshot(range(4))
            print('BASELINE',json.dumps(baseline),flush=True)

            # A: one validator stopped; remaining 3 of 4 must advance.
            stop(consensus[3])
            start_heights = [height(i) for i in (0,1,2)]
            wait_for(lambda: all(height(i)>=start_heights[j]+3 for j,i in enumerate((0,1,2))),90,'3-of-4 progress')
            three = snapshot((0,1,2))
            start_node(3,'-restart-a')
            wait_for(lambda: height(3)>=three['height']+1,90,'node 3 catch-up')
            wait_for(lambda: min(height(i) for i in range(4))>=three['height']+2,90,'post-restart progress')
            recovered = snapshot(range(4))
            results['one_validator_offline'] = {'result':'PASS','baseline':baseline,'three_node_progress':three,'recovered':recovered}
            print('ONE_VALIDATOR_OFFLINE PASS',flush=True)

            # B: stop two validators. A healthy 4-voter 10-power network
            # needs >2/3 voting power; 2 of 4 cannot commit new blocks.
            stop(consensus[2])
            stop(consensus[3])
            time.sleep(4)  # allow in-flight commits to settle before measurement
            if any(consensus[i].poll() is not None for i in (0,1)):
                raise AssertionError('surviving validator process exited')
            before = [height(i) for i in (0,1)]
            observation_seconds = 15
            time.sleep(observation_seconds)
            after = [height(i) for i in (0,1)]
            if after != before:
                raise AssertionError(f'blocks advanced without quorum: before={before}, after={after}')
            results['two_validators_offline'] = {'result':'PASS','before':before,'after':after,'observation_seconds':observation_seconds}
            print('TWO_VALIDATORS_OFFLINE PASS',flush=True)

            start_node(2,'-restart-b')
            start_node(3,'-restart-b')
            target = max(after)+3
            wait_for(lambda: all(height(i)>=target for i in range(4)),120,'quorum restoration')
            restored = snapshot(range(4))
            results['quorum_restoration'] = {'result':'PASS','converged':restored}
            print('QUORUM_RESTORATION PASS',flush=True)

            # C and D are not implemented here; fail closed on scope claims.
            results['two_two_network_partition'] = {'result':'NOT_IMPLEMENTED','reason':'requires actual P2P isolation with all validators running'}
            results['application_process_recovery'] = {'result':'NOT_IMPLEMENTED','reason':'requires controlled ABCI restart and state verification'}
            report = {'task':'009','phase':'A','result':'PASS_PHASE_A_ONLY','experiments':results}
            (ROOT/'task009-result.json').write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps(report,indent=2),flush=True)
        except Exception:
            for log in logs:
                log.flush()
            for path in sorted(tmp.glob('*.log')):
                print(f'\n===== {path.name} =====',file=sys.stderr)
                print('\n'.join(path.read_text(errors='replace').splitlines()[-35:]),file=sys.stderr)
            raise
        finally:
            for p in consensus+apps:
                if p is not None and p.poll() is None:
                    p.terminate()
            for p in consensus+apps:
                if p is not None and p.poll() is None:
                    try:
                        p.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        p.kill()
            for log in logs:
                log.close()


if __name__ == '__main__':
    main()
