#!/usr/bin/env python3
"""Isolated two-namespace NetEm calibration. Run only in disposable CI runners.

This is a network emulator, not evidence of satellite transport or consensus.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

OUT = Path('task019-calibration.json')
PREFIX = f'k19{os.getpid()}'
A, B = PREFIX+'a', PREFIX+'b'
VA, VB = 'v19a', 'v19b'


def run(*args, check=True):
    return subprocess.run(args, text=True, capture_output=True, check=check)


def command(*args):
    p = run(*args)
    return p.stdout.strip()


def ping(n, count=20):
    p = run('ip', 'netns', 'exec', n, 'ping', '-n', '-q', '-i', '0.1', '-W', '2', '-c', str(count), '10.219.19.2', check=False)
    output = p.stdout + p.stderr
    loss = re.search(r'(\d+(?:\.\d+)?)% packet loss', output)
    rtt = re.search(r'(?:rtt|round-trip) min/avg/max/(?:mdev|stddev) = [\d.]+/([\d.]+)/', output)
    if not loss:
        raise RuntimeError('Could not parse ping packet loss: '+output[-1500:])
    return {'sent': count, 'loss_pct': float(loss.group(1)), 'avg_rtt_ms': float(rtt.group(1)) if rtt else None, 'exit_code': p.returncode}


def main():
    result = {'kind':'KASPYRA Task 019 isolated NetEm calibration', 'satellite_verified':False,
              'consensus_tested':False, 'status':'FAIL', 'scenarios':[]}
    created = []
    try:
        if os.geteuid() != 0:
            raise RuntimeError('Root required inside disposable CI runner')
        for name in ('ip','tc','ping'):
            if not shutil.which(name):
                raise RuntimeError('Missing dependency: '+name)
        for n in (A,B):
            run('ip','netns','add',n)
            created.append(n)
        run('ip','link','add',VA,'type','veth','peer','name',VB)
        run('ip','link','set',VA,'netns',A)
        run('ip','link','set',VB,'netns',B)
        for n, iface, address in ((A,VA,'10.219.19.1/30'),(B,VB,'10.219.19.2/30')):
            run('ip','-n',n,'addr','add',address,'dev',iface)
            run('ip','-n',n,'link','set','lo','up')
            run('ip','-n',n,'link','set',iface,'up')
        # Baseline and calibrated two-way delays. Each interface contributes half the RTT.
        scenarios = [('baseline',0,0),('rtt_150ms',75,0),('rtt_300ms',150,0),('rtt_600ms',300,0),
                     ('jitter_loss',75,1)]
        for label, delay, loss in scenarios:
            for n, iface in ((A,VA),(B,VB)):
                if delay:
                    args=['ip','netns','exec',n,'tc','qdisc','replace','dev',iface,'root','netem',
                          'delay',f'{delay}ms']
                    if label=='jitter_loss':
                        args += ['20ms','distribution','normal']
                    if loss:
                        args += ['loss',f'{loss}%']
                    run(*args)
                else:
                    run('ip','netns','exec',n,'tc','qdisc','del','dev',iface,'root',check=False)
            configured={n:command('ip','netns','exec',n,'tc','qdisc','show','dev',iface)
                        for n,iface in ((A,VA),(B,VB))}
            if delay and not all('netem' in v and f'{delay}ms' in v for v in configured.values()):
                raise RuntimeError(f'NetEm not verified for {label}: {configured}')
            sample=ping(A, 100 if loss else 20)
            entry={'scenario':label,'target_rtt_ms':2*delay,'configured_loss_pct_per_direction':loss,
                   'qdisc':configured,'measurement':sample}
            result['scenarios'].append(entry)
            # Wide tolerance accounts for CI scheduling. This is calibration, not an SLA.
            if sample['avg_rtt_ms'] is None:
                raise RuntimeError(f'No successful ping samples in {label}')
            if delay and not (2*delay*0.65 <= sample['avg_rtt_ms'] <= 2*delay+125):
                raise RuntimeError(f'RTT out of bounds in {label}: {sample}')
            if not delay and sample['loss_pct'] != 0:
                raise RuntimeError('Baseline loss is nonzero')
        result['status']='PASS'
    except Exception as exc:
        result['error']=f'{type(exc).__name__}: {exc}'
    finally:
        for n in reversed(created):
            run('ip','netns','del',n,check=False)
        OUT.write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result,indent=2))
    return 0 if result['status']=='PASS' else 1

if __name__=='__main__':
    sys.exit(main())
