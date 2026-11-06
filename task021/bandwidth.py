#!/usr/bin/env python3
"""Four real CometBFT validators in isolated Linux namespaces with NetEm.
Disposable GitHub-hosted runner ONLY. No satellite transport is claimed.
"""
import json, os, pathlib, re, shutil, subprocess, sys, tempfile, time

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'task021-bandwidth-evidence.json'
CHAIN='kaspyra-task021-bandwidth'
PREFIX=f'k21v{os.getpid()}'
BRIDGE=PREFIX[:12]+'b'
NS=[PREFIX+str(i) for i in range(4)]
HOST=[f'kh21{i}' for i in range(4)]
GUEST=[f'kg21{i}' for i in range(4)]
IPS=[f'10.221.20.{i+2}' for i in range(4)]

def run(*args,check=True,**kw):
    result = subprocess.run(
        [str(x) for x in args],
        text=True,
        capture_output=True,
        check=False,
        **kw
    )
    if check and result.returncode:
        raise RuntimeError(
            f"Command failed: {args!r} (exit {result.returncode})\n"
            f"STDOUT:\n{result.stdout[-4000:]}\n"
            f"STDERR:\n{result.stderr[-4000:]}"
        )
    return result

def cmd(*args): return run(*args).stdout.strip()
def net(i,*args,**kw): return run('ip','netns','exec',NS[i],*args,**kw)
def replace_toml(path,section,key,value):
    lines=path.read_text().splitlines(); current=None; done=False; output=[]
    for line in lines:
        m=re.match(r'^\s*\[([^]]+)\]',line)
        if m: current=m.group(1)
        if current==section and re.match(r'^\s*'+re.escape(key)+r'\s*=',line):
            line=f'{key} = {json.dumps(value)}'; done=True
        output.append(line)
    if not done: raise RuntimeError(f'Missing {section}.{key}')
    path.write_text('\n'.join(output)+'\n')

def rpc(i,endpoint,**params):
    from urllib.parse import urlencode
    # Run inside namespace; localhost RPC is inaccessible from root namespace.
    code='import json,sys,urllib.request;print(json.dumps(json.load(urllib.request.urlopen(sys.argv[1],timeout=4))))'
    url=f'http://127.0.0.1:26657/{endpoint}?{urlencode(params)}'
    response=json.loads(net(i,sys.executable,'-c',code,url).stdout)
    if 'error' in response: raise RuntimeError(response['error'])
    return response['result']

def height(i): return int(rpc(i,'status')['sync_info']['latest_block_height'])
def peers(i): return {p['node_info']['id'] for p in rpc(i,'net_info')['peers']}
def wait(fn,timeout,label):
    end=time.monotonic()+timeout; last=None
    while time.monotonic()<end:
        try:
            value=fn()
            if value:return value
        except Exception as e:last=e
        time.sleep(1)
    raise RuntimeError(f'Timeout {label}: {last}')

def snapshot():
    h=[height(i) for i in range(4)]; common=min(h)
    if common<2: raise RuntimeError('Insufficient block height')
    blocks=[]
    for i in range(4):
        b=rpc(i,'block',height=common)
        blocks.append((b['block_id']['hash'],b['block']['header']['app_hash']))
    if len(set(blocks))!=1: raise RuntimeError(f'Block/app hash divergence at {common}: {blocks}')
    return {'heights':h,'common_height':common,'block_hash':blocks[0][0],'app_hash':blocks[0][1]}

def network_create(created):
    run('ip','link','add',BRIDGE,'type','bridge'); created.append(('bridge',BRIDGE))
    run('ip','link','set',BRIDGE,'up')
    for i in range(4):
        run('ip','netns','add',NS[i]);created.append(('ns',NS[i]))
        run('ip','link','add',HOST[i],'type','veth','peer','name',GUEST[i])
        run('ip','link','set',HOST[i],'master',BRIDGE)
        run('ip','link','set',HOST[i],'up')
        run('ip','link','set',GUEST[i],'netns',NS[i])
        run('ip','-n',NS[i],'addr','add',IPS[i]+'/24','dev',GUEST[i])
        run('ip','-n',NS[i],'link','set','lo','up')
        run('ip','-n',NS[i],'link','set',GUEST[i],'up')
    for i in range(4):
        for j in range(4):
            if i!=j and net(i,'ping','-c','1','-W','2',IPS[j],check=False).returncode!=0:
                raise RuntimeError(f'No connectivity from {i} to {j}')

def shape(rtt,jitter=0,loss=0):
    # Four egress interfaces per round trip: guest->host->guest->host.
    # Each hop contributes RTT/4. All validators use the same qdisc settings.
    delay=rtt/4
    for i in range(4):
        for base,iface in ((('ip','netns','exec',NS[i]),GUEST[i]),((),HOST[i])):
            pre=(*base,'tc') if base else ('tc',)
            if rtt:
                args=[*pre,'qdisc','replace','dev',iface,'root','netem','delay',f'{delay:.3f}ms']
                if jitter: args += [f'{jitter/4:.3f}ms']
                if loss: args += ['loss',f'{loss}%']
                run(*args)
                value=cmd(*pre,'qdisc','show','dev',iface)
                if 'netem' not in value: raise RuntimeError(f'Missing netem: {iface}: {value}')
            else:
                run(*pre,'qdisc','del','dev',iface,'root',check=False)
    return {str(i):{'guest':cmd('ip','netns','exec',NS[i],'tc','qdisc','show','dev',GUEST[i]),
                    'host':cmd('tc','qdisc','show','dev',HOST[i])} for i in range(4)}

def measure_rtt():
    output=net(0,'ping','-n','-q','-i','0.2','-W','2','-c','8',IPS[1],check=False)
    match=re.search(r'(?:rtt|round-trip) min/avg/max/(?:mdev|stddev) = [\d.]+/([\d.]+)/',output.stdout)
    if output.returncode!=0 or not match:
        raise RuntimeError('Failed to measure validator-link RTT: '+(output.stdout+output.stderr)[-500:])
    return float(match.group(1))

def partition(enable, majority=(0, 1)):
    # Namespace-local routes. Never change host networking.
    for i in range(4):
        for j in range(4):
            if (i in majority) != (j in majority):
                op = 'replace' if enable else 'del'
                run(
                    'ip', '-n', NS[i], 'route',
                    op, 'unreachable', IPS[j] + '/32',
                    check=True
                )

    if enable:
        # Both directions of every cross-group connection must fail.
        for i in range(4):
            for j in range(4):
                if (i in majority) != (j in majority):
                    result = net(
                        i, 'ping', '-c', '1', '-W', '1',
                        IPS[j], check=False
                    )
                    if result.returncode == 0:
                        raise RuntimeError(
                            f'Partition isolation failed: {i}->{j}'
                        )

def main():
    report={'task':'021A','phase':'consensus-bandwidth','status':'FAIL','satellite_verified':False,
            'environment':'isolated Linux namespaces in disposable CI','scenarios':[]}
    created=[]; processes=[]; logs=[]
    try:
        if os.geteuid()!=0:raise RuntimeError('Must run as root in disposable CI')
        for tool in ('ip','tc','ping','go','cometbft'):
            if not shutil.which(tool):raise RuntimeError(f'Missing {tool}')
        with tempfile.TemporaryDirectory(prefix='kaspyra020-') as directory:
            tmp=pathlib.Path(directory); binary=tmp/'abci'
            run('go','build','-o',binary,'.',cwd=ROOT/'task008c')
            network_create(created)
            nodes=[]
            for i in range(4):
                home=tmp/f'node{i}';home.mkdir()
                run('cometbft','init','validator','--home',home)
                key=json.loads((home/'config/priv_validator_key.json').read_text())
                nid=cmd('cometbft','show-node-id','--home',home)
                nodes.append((home,key,nid))
            genesis=json.loads((nodes[0][0]/'config/genesis.json').read_text())
            genesis.update(chain_id=CHAIN,app_hash='',validators=[
                {'address':key['address'],'pub_key':key['pub_key'],'power':'10','name':f'kaspyra-{i}'}
                for i,(_,key,_) in enumerate(nodes)])
            for i,(home,_,_) in enumerate(nodes):
                (home/'config/genesis.json').write_text(json.dumps(genesis))
                (home/'balances.json').write_text(json.dumps({'a'*40:1000,'b'*40:0}))
                config=home/'config/config.toml'
                replace_toml(config,'p2p','laddr','tcp://0.0.0.0:26656')
                replace_toml(config,'rpc','laddr','tcp://127.0.0.1:26657')
                replace_toml(config,None,'proxy_app','tcp://127.0.0.1:26658')
                replace_toml(config,'p2p','persistent_peers',','.join(
                    f'{nodes[j][2]}@{IPS[j]}:26656' for j in range(4) if i!=j))
                replace_toml(config,'p2p','pex',False)
                replace_toml(config,'p2p','addr_book_strict',False)
                replace_toml(config,'consensus','timeout_commit','1s')
                replace_toml(config,'consensus','create_empty_blocks',True)
                replace_toml(config,'consensus','create_empty_blocks_interval','0s')
            def launch(i,argv,name):
                log=open(tmp/f'{name}{i}.log','w');logs.append(log)
                proc=subprocess.Popen(['ip','netns','exec',NS[i],*map(str,argv)],stdout=log,stderr=subprocess.STDOUT)
                processes.append(proc)
            for i,(home,_,_) in enumerate(nodes):
                launch(i,[binary,'-listen','tcp://127.0.0.1:26658','-state',home/'data/appstate.json',
                          '-chain',CHAIN,'-balances',home/'balances.json'],'app')
            time.sleep(2)
            for i,(home,_,_) in enumerate(nodes): launch(i,['cometbft','node','--home',home],'node')
            wait(lambda: min(height(i) for i in range(4))>=4,120,'baseline blocks')
            wait(lambda: all(len(peers(i))>=3 for i in range(4)),90,'full peer mesh')
            report['baseline']=snapshot()
            # Read kernel counters inside each namespace, on validator-facing veth.
            # These include P2P, ICMP, Ethernet/IP/TCP overhead and retransmissions.
            # RPC stays on loopback and is excluded. No transactions are submitted.
            def counters():
                data=[]
                for i in range(4):
                    entry={}
                    for key in ('rx_bytes','tx_bytes','rx_packets','tx_packets'):
                        path=f'/sys/class/net/{GUEST[i]}/statistics/{key}'
                        entry[key]=int(net(i,'cat',path).stdout.strip())
                    data.append(entry)
                return data

            def sample(label,seconds):
                before=counters()
                initial=snapshot()
                started=time.monotonic()
                time.sleep(seconds)
                elapsed=time.monotonic()-started
                after=counters()
                final=snapshot()
                deltas=[{key:after[i][key]-before[i][key] for key in before[i]}
                        for i in range(4)]
                if any(v<0 for d in deltas for v in d.values()):
                    raise RuntimeError('Negative interface counter delta')
                block_delta=final['common_height']-initial['common_height']
                if block_delta<=0:
                    raise RuntimeError(f'{label}: no consensus progress')
                result={'name':label,'elapsed_s':round(elapsed,3),
                        'initial':initial,'final':final,'common_blocks_added':block_delta,
                        'per_validator':[],
                        'aggregate_tx_bytes':sum(d['tx_bytes'] for d in deltas),
                        'aggregate_rx_bytes':sum(d['rx_bytes'] for d in deltas)}
                for i,d in enumerate(deltas):
                    result['per_validator'].append({'validator':i,**d,
                        'tx_bytes_per_s':round(d['tx_bytes']/elapsed,2),
                        'rx_bytes_per_s':round(d['rx_bytes']/elapsed,2),
                        'tx_bytes_per_common_block':round(d['tx_bytes']/block_delta,2)})
                report['scenarios'].append(result)
                return result

            sample('baseline_empty_blocks',30)
            qdisc=shape(300)
            report['rtt300_qdisc']=qdisc
            report['rtt300_measured_ms']=measure_rtt()
            sample('rtt300_empty_blocks',30)
            shape(0)
            wait(lambda:all(len(peers(i))>=3 for i in range(4)),120,'peers before outage')
            before=counters()
            pre=snapshot()
            for i in range(4):
                for j in range(4):
                    if i!=j:
                        run('ip','-n',NS[i],'route','replace','unreachable',IPS[j]+'/32')
            time.sleep(5)
            stalled=[height(i) for i in range(4)]
            time.sleep(15)
            if [height(i) for i in range(4)]!=stalled:
                raise RuntimeError('Unexpected progress in blackout')
            for i in range(4):
                for j in range(4):
                    if i!=j:
                        run('ip','-n',NS[i],'route','del','unreachable',IPS[j]+'/32')
            resumed=time.monotonic()
            wait(lambda:all(len(peers(i))>=3 for i in range(4)),150,'peer recovery')
            wait(lambda:min(height(i) for i in range(4))>=max(stalled)+3,180,'block recovery')
            recovery_s=time.monotonic()-resumed
            after=counters()
            report['recovery']={'before':pre,'after':snapshot(),
                'recovery_s':round(recovery_s,3),
                'per_validator_total_interface_bytes_during_outage_and_recovery':[
                    {key:after[i][key]-before[i][key] for key in ('rx_bytes','tx_bytes')}
                    for i in range(4)],
                'note':'Includes blackout and reconnection; not isolated catch-up traffic.'}
            report['limitations']=[
                'Synthetic local namespaces; not satellite transport.',
                'Empty blocks only: no transaction throughput measurement.',
                'Interface counters include L2/L3 overhead and background P2P traffic.',
                'Per-block averages include consensus background traffic; not marginal cost per block.',
                'Recovery traffic includes outage and reconnection, not separately attributable.',
                'No peak/percentile bandwidth measurement from coarse 30-second windows.'
            ]
            report['status'] = 'PASS'
    except Exception as exc:
        report['error']=f'{type(exc).__name__}: {exc}'
        if 'tmp' in locals():
            for log in logs:log.flush()
            for p in sorted(tmp.glob('*.log')):
                print(f'--- {p.name} ---\n'+ '\n'.join(p.read_text(errors='replace').splitlines()[-30:]),file=sys.stderr)
    finally:
        for p in processes:
            if p.poll() is None:p.terminate()
        for p in processes:
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:p.kill();p.wait()
        for log in logs:log.close()
        for typ,name in reversed(created):
            if typ=='ns':run('ip','netns','del',name,check=False)
            else:run('ip','link','del',name,check=False)
        OUT.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2),flush=True)
    return 0 if report['status'].startswith('PASS') else 1

if __name__=='__main__':sys.exit(main())