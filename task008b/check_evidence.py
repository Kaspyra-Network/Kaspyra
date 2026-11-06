"""Validate evidence manifest shape; does NOT prove CometBFT behavior."""
import json
import pathlib
import sys

REQUIRED = ('cometbft_version','commit','ci_run_url','nodes','transfer_tx_hash','quorum_loss','quorum_recovery','restart','crash_replay')

def validate(data):
    missing = [k for k in REQUIRED if k not in data]
    if missing:
        raise ValueError('missing fields: ' + ', '.join(missing))
    nodes = data['nodes']
    if not isinstance(nodes, list) or len(nodes) != 4:
        raise ValueError('four node observations required')
    heights = [n['height'] for n in nodes]
    hashes = [n['app_hash'] for n in nodes]
    if any(not isinstance(h, int) or h < 1 for h in heights):
        raise ValueError('invalid heights')
    if len(set(hashes)) != 1 or not hashes[0]:
        raise ValueError('app hash mismatch')
    if len(set(heights)) != 1:
        raise ValueError('node heights differ')
    if not all(data[k] is True for k in ('quorum_loss','quorum_recovery','restart','crash_replay')):
        raise ValueError('recovery checks not confirmed')
    return True

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: python check_evidence.py evidence.json')
    validate(json.loads(pathlib.Path(sys.argv[1]).read_text()))
    print('Manifest structurally complete (NOT independently verified).')
