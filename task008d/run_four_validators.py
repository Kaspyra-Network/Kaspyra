#!/usr/bin/env python3
"""Local-only CometBFT four-validator smoke test. Requires task008c binary and cometbft CLI.
NOT a Byzantine fault tolerance or partition-safety proof.
"""
import base64, hashlib, json, os, pathlib, re, shutil, subprocess, sys, tempfile, time, urllib.parse, urllib.request
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

CHAIN='kaspyra-local-008c'

def cmd(*args, **kw):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT, **kw).strip()

def rpc(port, endpoint, **params):
    query=urllib.parse.urlencode(params)
    with urllib.request.urlopen(f'http://127.0.0.1:{port}/{endpoint}?{query}', timeout=4) as r:
        obj=json.load(r)
    if 'error' in obj: raise RuntimeError(obj['error'])
    return obj['result']

def wait_until(fn, seconds=90):
    deadline=time.monotonic()+seconds
    last=None
    while time.monotonic()<deadline:
        try:
            value=fn()
            if value: return value
        except Exception as e: last=e
        time.sleep(1)
    raise TimeoutError(f'timed out: {last}')

def replace_toml(path, key, value, section=None):
    data=path.read_text(); current=None; found=False; out=[]
    for line in data.splitlines():
        match=re.match(r'^\s*\[([^]]+)\]\s*$',line)
        if match: current=match.group(1)
        if current==section and re.match(r'^\s*'+re.escape(key)+r'\s*=',line):
            line=f'{key} = {json.dumps(value)}'; found=True
        out.append(line)
    if not found: raise RuntimeError(f'{key} not found in [{section}] in {path}')
    path.write_text('\n'.join(out)+'\n')

def main():
    for executable in ('cometbft','go'):
        if not shutil.which(executable): raise RuntimeError(f'{executable} is required')
    root=pathlib.Path(__file__).resolve().parents[2]
    source=root/'task008c'
    if not (source/'go.mod').exists(): raise RuntimeError('task008c/ must exist alongside task008d/')
    with tempfile.TemporaryDirectory(prefix='kaspyra-008d-') as temp:
        tmp=pathlib.Path(temp); binary=tmp/'kaspyra-abci'
        subprocess.run(['go','build','-o',str(binary),'.'],cwd=source,check=True)
        nodes=[]; processes=[]; logs=[]
        try:
            # Fresh keys for every run; all four nodes share a genesis with four validators.
            for i in range(4):
                home=tmp/f'node{i}'; home.mkdir()
                cmd('cometbft','init','validator','--home',str(home))
                key=json.loads((home/'config/priv_validator_key.json').read_text())
                node_id=cmd('cometbft','show-node-id','--home',str(home))
                nodes.append((home,key,node_id))
            validators=[{'address':key['address'],'pub_key':key['pub_key'],'power':'10','name':f'kaspyra-{i}'} for i,(_,key,_) in enumerate(nodes)]
            genesis=json.loads((nodes[0][0]/'config/genesis.json').read_text())
            genesis['chain_id']=CHAIN; genesis['validators']=validators; genesis['app_hash']=''
            # Explicit deterministic development accounts, never production credentials.
            sender=Ed25519PrivateKey.generate(); receiver=Ed25519PrivateKey.generate()
            pub=sender.public_key().public_bytes(encoding=serialization.Encoding.Raw,format=serialization.PublicFormat.Raw)
            rpub=receiver.public_key().public_bytes(encoding=serialization.Encoding.Raw,format=serialization.PublicFormat.Raw)
            src=hashlib.sha256(pub).hexdigest()[:40]; dst=hashlib.sha256(rpub).hexdigest()[:40]
            balances={src:1000,dst:0}
            for i,(home,_,_) in enumerate(nodes):
                (home/'config/genesis.json').write_text(json.dumps(genesis,indent=2)+'\n')
                (home/'balances.json').write_text(json.dumps(balances)+'\n')
                conf=home/'config/config.toml'
                # Different ports on loopback; peers are explicitly enumerated.
                replace_toml(conf,'laddr',f'tcp://127.0.0.1:{26656+i*10}', 'p2p')
                replace_toml(conf,'laddr',f'tcp://127.0.0.1:{26657+i*10}', 'rpc')
                replace_toml(conf,'proxy_app',f'tcp://127.0.0.1:{26658+i*10}', None)
                peers=','.join(f'{nid}@127.0.0.1:{26656+j*10}' for j,(_,_,nid) in enumerate(nodes) if j!=i)
                replace_toml(conf,'persistent_peers',peers,'p2p')
                replace_toml(conf,'addr_book_strict',False,'p2p')
                replace_toml(conf,'allow_duplicate_ip',True,'p2p')
                replace_toml(conf,'timeout_commit','1s','consensus')
                replace_toml(conf,'create_empty_blocks',True,'consensus')
                replace_toml(conf,'create_empty_blocks_interval','0s','consensus')
                logs.append(open(tmp/f'app{i}.log','w'))
                processes.append(subprocess.Popen([str(binary),'-listen',f'tcp://127.0.0.1:{26658+i*10}','-state',str(home/'data/appstate.json'),'-chain',CHAIN,'-balances',str(home/'balances.json')],stdout=logs[-1],stderr=subprocess.STDOUT))
            time.sleep(2)
            for i,(home,_,_) in enumerate(nodes):
                logs.append(open(tmp/f'consensus{i}.log','w'))
                processes.append(subprocess.Popen(['cometbft','node','--home',str(home)],stdout=logs[-1],stderr=subprocess.STDOUT))
            wait_until(lambda: all(int(rpc(26657+i*10,'status')['sync_info']['latest_block_height'])>=3 for i in range(4)),120)
            payload={'chain_id':CHAIN,'from':src,'to':dst,'amount':125,'nonce':0}
            wire=json.dumps(payload,separators=(',',':')).encode()
            sig=sender.sign(wire).hex()
            tx={**payload,'public_key':pub.hex(),'signature':sig}
            raw=json.dumps(tx,separators=(',',':')).encode().hex()
            result=rpc(26657,'broadcast_tx_sync',tx='0x'+raw)
            if result['code']!=0: raise AssertionError(f'tx rejected: {result}')
            txhash=result['hash']
            txinfo=wait_until(lambda: rpc(26657,'tx',hash='0x'+txhash,prove='false'),90)
            if txinfo['tx_result']['code']!=0: raise AssertionError(f'tx failed: {txinfo}')
            height=int(txinfo['height'])
            wait_until(lambda: all(int(rpc(26657+i*10,'status')['sync_info']['latest_block_height'])>=height+2 for i in range(4)),90)
            # At same block height compare finalized app_hash (not latest, which can race).
            hashes=[rpc(26657+i*10,'block',height=height+1)['block']['header']['app_hash'] for i in range(4)]
            if len(set(hashes))!=1: raise AssertionError(f'app hashes diverged: {hashes}')
            for home,_,_ in nodes:
                state=json.loads((home/'data/appstate.json').read_text())
                if state['accounts'][src]['balance']!=875 or state['accounts'][dst]['balance']!=125:
                    raise AssertionError('wrong persisted balances')
            # Restart one consensus node and ensure it catches up.
            processes[5].terminate(); processes[5].wait(timeout=15)
            home=nodes[1][0]; logs.append(open(tmp/'consensus1-restart.log','w'))
            processes.append(subprocess.Popen(['cometbft','node','--home',str(home)],stdout=logs[-1],stderr=subprocess.STDOUT))
            wait_until(lambda: int(rpc(26667,'status')['sync_info']['latest_block_height'])>=height+3,90)
            print(json.dumps({'result':'PASS','chain_id':CHAIN,'validators':4,'transfer':125,'tx_hash':txhash,'finalized_height':height,'matching_app_hash':hashes[0],'validator_restart':'PASS'},indent=2))
        except Exception:
            for log in logs:
                try: log.flush()
                except Exception: pass
            for p in (tmp.glob('*.log')):
                print(f'\n===== {p.name} (last 25 lines) =====',file=sys.stderr)
                print('\n'.join(p.read_text(errors='replace').splitlines()[-25:]),file=sys.stderr)
            raise
        finally:
            for p in processes:
                if p.poll() is None: p.terminate()
            for p in processes:
                if p.poll() is None:
                    try: p.wait(timeout=5)
                    except subprocess.TimeoutExpired: p.kill()
            for log in logs: log.close()

if __name__=='__main__': main()
