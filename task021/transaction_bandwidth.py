#!/usr/bin/env python3
"""Four real CometBFT validators in isolated Linux namespaces with NetEm.
Disposable GitHub-hosted runner ONLY. No satellite transport is claimed.
"""
import json, os, pathlib, re, shutil, subprocess, sys, tempfile, time

ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'task021b-bandwidth-evidence.json'
CHAIN='kaspyra-task021b-bandwidth'
PREFIX=f'k21bv{os.getpid()}'
BRIDGE=PREFIX[:12]+'b'
NS=[PREFIX+str(i) for i in range(4)]
HOST=[f'kh21b{i}' for i in range(4)]
GUEST=[f'kg21b{i}' for i in range(4)]
IPS=[f'10.221.21.{i+2}' for i in range(4)]

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
    report={'task':'021B','phase':'transaction-bandwidth','status':'FAIL','satellite_verified':False,
            'environment':'isolated Linux namespaces in disposable CI','scenarios':[]}
    created=[]; processes=[]; logs=[]
    try:
        if os.geteuid()!=0:raise RuntimeError('Must run as root in disposable CI')
        for tool in ('ip','tc','ping','go','cometbft'):
            if not shutil.which(tool):raise RuntimeError(f'Missing {tool}')
        with tempfile.TemporaryDirectory(prefix='kaspyra021b-') as directory:
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
            txgen_binary=tmp/'txgen'
            run('go','build','-o',txgen_binary,'task021/txgen.go',cwd=ROOT)
            # Fund four deterministic TEST-ONLY accounts for independent nonces.
            funding={}
            for i in range(4):
                import hashlib
                # Go generator uses SHA256 seed and Ed25519 address derivation.
                # Query generator itself to avoid Python cryptography dependencies.
                generated=run(txgen_binary,CHAIN,i,0).stdout.strip()
                address=json.loads(bytes.fromhex(generated))['from']
                funding[address]=10000
            genesis=json.loads((nodes[0][0]/'config/genesis.json').read_text())
            genesis.update(chain_id=CHAIN,app_hash='',validators=[
                {'address':key['address'],'pub_key':key['pub_key'],'power':'10','name':f'kaspyra-{i}'}
                for i,(_,key,_) in enumerate(nodes)])
            for i,(home,_,_) in enumerate(nodes):
                (home/'config/genesis.json').write_text(json.dumps(genesis))
                (home/'balances.json').write_text(json.dumps({**funding,'b'*40:0}))
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
            # Namespace veth counters exclude RPC loopback traffic.
            def counters():
                result=[]
                for i in range(4):
                    entry={}
                    for key in ('rx_bytes','tx_bytes','rx_packets','tx_packets'):
                        entry[key]=int(net(i,'cat',f'/sys/class/net/{GUEST[i]}/statistics/{key}').stdout.strip())
                    result.append(entry)
                return result

            def tx_hex(sender,nonce):
                return run(txgen_binary,CHAIN,sender,nonce).stdout.strip()

            # Pre-generate signed fixtures outside the measurement windows.
            fixtures={(sender,nonce):tx_hex(sender,nonce) for sender in range(4) for nonce in range(24)}
            nonces=[0]*4
            from concurrent.futures import ThreadPoolExecutor
            import threading
            def transmit(sender):
                nonce=nonces[sender]
                result=rpc(sender,'broadcast_tx_commit',tx='0x'+fixtures[sender,nonce])
                check=result['check_tx']; deliver=result['tx_result']
                if int(check['code'])!=0 or int(deliver['code'])!=0:
                    raise RuntimeError(f'Tx rejected sender={sender} nonce={nonce}: {result}')
                nonces[sender]+=1
                return result['hash']

            def measure(label,seconds,rate):
                # Rate is offered TPS, not assumed committed TPS.
                initial=snapshot(); first=counters(); samples=[]; sent=[]
                started=time.monotonic(); stop=threading.Event()
                def poll():
                    while not stop.is_set():
                        now=time.monotonic()
                        samples.append((now,counters()))
                        stop.wait(1)
                monitor=threading.Thread(target=poll,daemon=True);monitor.start()
                try:
                    if rate:
                        with ThreadPoolExecutor(max_workers=4) as pool:
                            pending=[]; slot=0
                            while time.monotonic()-started<seconds:
                                due=started+slot/rate
                                delay=due-time.monotonic()
                                if delay>0:time.sleep(delay)
                                if time.monotonic()-started>=seconds:break
                                sender=slot%4
                                # One outstanding tx per sender; avoid duplicate nonce.
                                if pending and len(pending)>=4:
                                    done=pending.pop(0);sent.append(done.result())
                                pending.append(pool.submit(transmit,sender))
                                slot+=1
                            for f in pending:sent.append(f.result())
                    else:time.sleep(seconds)
                finally:
                    stop.set();monitor.join(timeout=5)
                ended=time.monotonic();last=counters();final=snapshot()
                samples.append((ended,last))
                per=[]
                for i in range(4):
                    d={key:last[i][key]-first[i][key] for key in first[i]}
                    if min(d.values())<0:raise RuntimeError('Negative counter delta')
                    intervals=[]
                    for (t0,c0),(t1,c1) in zip(samples,samples[1:]):
                        dt=t1-t0
                        if dt>0.1:intervals.append(8*(c1[i]['tx_bytes']-c0[i]['tx_bytes'])/dt)
                    intervals.sort()
                    p95=intervals[min(len(intervals)-1,int(.95*(len(intervals)-1)))] if intervals else None
                    per.append({'validator':i,**d,'tx_bytes_per_s':round(d['tx_bytes']/(ended-started),2),
                                'rx_bytes_per_s':round(d['rx_bytes']/(ended-started),2),
                                'peak_observed_tx_bps':round(max(intervals),2) if intervals else None,
                                'p95_observed_tx_bps':round(p95,2) if p95 is not None else None})
                if final['common_height']<=initial['common_height']:raise RuntimeError(f'{label}: no progress')
                if rate and len(sent)==0:raise RuntimeError(f'{label}: no accepted transactions')
                record={'name':label,'offered_tps':rate,'elapsed_s':round(ended-started,3),
                        'committed_transactions_acknowledged':len(sent),
                        'observed_committed_tps':round(len(sent)/(ended-started),3),
                        'initial':initial,'final':final,'per_validator':per,
                        'sample_count':len(samples),'sample_interval_target_s':1,
                        'peak_measurement':'one-second interface counter deltas; not physical link instantaneous peak'}
                report['scenarios'].append(record)
                return record

            measure('empty_blocks_20s',20,0)
            measure('target_0_5_tps',20,0.5)
            measure('target_1_tps',20,1)
            measure('target_2_tps',20,2)
            # Reconnect after outage and measure separately from blackout.
            wait(lambda:all(len(peers(i))>=3 for i in range(4)),90,'pre-outage peer mesh')
            for i in range(4):
                for j in range(4):
                    if i!=j:run('ip','-n',NS[i],'route','replace','unreachable',IPS[j]+'/32')
            time.sleep(5);stall=[height(i) for i in range(4)]
            time.sleep(10)
            if [height(i) for i in range(4)]!=stall:raise RuntimeError('Consensus progressed during outage')
            for i in range(4):
                for j in range(4):
                    if i!=j:run('ip','-n',NS[i],'route','del','unreachable',IPS[j]+'/32')
            recovered_at=time.monotonic(); recovery_first=counters()
            wait(lambda:all(len(peers(i))>=3 for i in range(4)),120,'peer recovery')
            wait(lambda:min(height(i) for i in range(4))>=max(stall)+3,150,'consensus recovery')
            recovery_last=counters();report['recovery']={
                'elapsed_s':round(time.monotonic()-recovered_at,3),'before_heights':stall,
                'after':snapshot(),'bytes_after_routes_restored':[
                    {key:recovery_last[i][key]-recovery_first[i][key] for key in ('rx_bytes','tx_bytes')}
                    for i in range(4)]}
            report['limitations']=[
                'Synthetic CI network, not actual satellite connectivity.',
                'Small number of deterministic signed transfers; not representative production load.',
                'Offered TPS is not guaranteed achieved TPS; RPC broadcast_tx_commit is synchronous.',
                'Per-second sampling may miss subsecond bursts.',
                'Counter deltas include L2/L3 overhead and P2P retransmissions.',
                'Recovery measures resumed empty-block consensus; no backlog of queued transactions.',
                'Deterministic private keys are fixtures and MUST NEVER be used with real assets.'
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