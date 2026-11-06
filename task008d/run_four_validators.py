
#!/usr/bin/env python3
"""Local-only CometBFT four-validator smoke test.

Requires task008c Go application and cometbft CLI.
NOT a Byzantine fault tolerance or partition-safety proof.
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

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

CHAIN = "kaspyra-local-008c"


def cmd(*args, **kw):
    return subprocess.check_output(
        args, text=True, stderr=subprocess.STDOUT, **kw
    ).strip()


def rpc(port, endpoint, **params):
    query = urllib.parse.urlencode(params)
    url = f"http://127.0.0.1:{port}/{endpoint}?{query}"

    with urllib.request.urlopen(url, timeout=4) as response:
        obj = json.load(response)

    if "error" in obj:
        raise RuntimeError(obj["error"])

    return obj["result"]


def wait_until(fn, seconds=90):
    deadline = time.monotonic() + seconds
    last = None

    while time.monotonic() < deadline:
        try:
            value = fn()
            if value:
                return value
        except Exception as exc:
            last = exc

        time.sleep(1)

    raise TimeoutError(f"timed out: {last}")


def replace_toml(path, key, value, section=None):
    data = path.read_text()
    current = None
    found = False
    out = []

    for line in data.splitlines():
        match = re.match(r"^\s*\[([^]]+)\]\s*$", line)

        if match:
            current = match.group(1)

        if current == section and re.match(
            r"^\s*" + re.escape(key) + r"\s*=", line
        ):
            line = f"{key} = {json.dumps(value)}"
            found = True

        out.append(line)

    if not found:
        raise RuntimeError(
            f"{key} not found in [{section}] in {path}"
        )

    path.write_text("\n".join(out) + "\n")


def main():
    for executable in ("cometbft", "go"):
        if not shutil.which(executable):
            raise RuntimeError(f"{executable} is required")

    # Correct repository root:
    # Kaspyra/task008d/run_four_validators.py
    # parents[0] = task008d
    # parents[1] = Kaspyra
    root = pathlib.Path(__file__).resolve().parents[1]
    source = root / "task008c"

    if not (source / "go.mod").exists():
        raise RuntimeError(
            f"Task 008C Go module not found: {source / 'go.mod'}"
        )

    with tempfile.TemporaryDirectory(
        prefix="kaspyra-008d-"
    ) as temp:
        tmp = pathlib.Path(temp)
        binary = tmp / "kaspyra-abci"

        subprocess.run(
            ["go", "build", "-o", str(binary), "."],
            cwd=source,
            check=True,
        )

        nodes = []
        processes = []
        logs = []

        try:
            # Initialize four independent validator identities.
            for i in range(4):
                home = tmp / f"node{i}"
                home.mkdir()

                cmd(
                    "cometbft",
                    "init",
                    "validator",
                    "--home",
                    str(home),
                )

                key = json.loads(
                    (home / "config/priv_validator_key.json").read_text()
                )

                node_id = cmd(
                    "cometbft",
                    "show-node-id",
                    "--home",
                    str(home),
                )

                nodes.append((home, key, node_id))

            validators = [
                {
                    "address": key["address"],
                    "pub_key": key["pub_key"],
                    "power": "10",
                    "name": f"kaspyra-{i}",
                }
                for i, (_, key, _) in enumerate(nodes)
            ]

            genesis = json.loads(
                (nodes[0][0] / "config/genesis.json").read_text()
            )

            genesis["chain_id"] = CHAIN
            genesis["validators"] = validators
            genesis["app_hash"] = ""

            # Development-only accounts.
            sender = Ed25519PrivateKey.generate()
            receiver = Ed25519PrivateKey.generate()

            pub = sender.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )

            rpub = receiver.public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )

            src = hashlib.sha256(pub).hexdigest()[:40]
            dst = hashlib.sha256(rpub).hexdigest()[:40]

            balances = {
                src: 1000,
                dst: 0,
            }

            for i, (home, _, _) in enumerate(nodes):
                (home / "config/genesis.json").write_text(
                    json.dumps(genesis, indent=2) + "\n"
                )

                (home / "balances.json").write_text(
                    json.dumps(balances) + "\n"
                )

                conf = home / "config/config.toml"

                replace_toml(
                    conf,
                    "laddr",
                    f"tcp://127.0.0.1:{26656 + i * 10}",
                    "p2p",
                )

                replace_toml(
                    conf,
                    "laddr",
                    f"tcp://127.0.0.1:{26657 + i * 10}",
                    "rpc",
                )

                replace_toml(
                    conf,
                    "proxy_app",
                    f"tcp://127.0.0.1:{26658 + i * 10}",
                    None,
                )

                peers = ",".join(
                    f"{nid}@127.0.0.1:{26656 + j * 10}"
                    for j, (_, _, nid) in enumerate(nodes)
                    if j != i
                )

                replace_toml(
                    conf,
                    "persistent_peers",
                    peers,
                    "p2p",
                )

                replace_toml(
                    conf,
                    "addr_book_strict",
                    False,
                    "p2p",
                )

                replace_toml(
                    conf,
                    "allow_duplicate_ip",
                    True,
                    "p2p",
                )

                replace_toml(
                    conf,
                    "timeout_commit",
                    "1s",
                    "consensus",
                )

                replace_toml(
                    conf,
                    "create_empty_blocks",
                    True,
                    "consensus",
                )

                replace_toml(
                    conf,
                    "create_empty_blocks_interval",
                    "0s",
                    "consensus",
                )

                log = open(tmp / f"app{i}.log", "w")
                logs.append(log)

                processes.append(
                    subprocess.Popen(
                        [
                            str(binary),
                            "-listen",
                            f"tcp://127.0.0.1:{26658 + i * 10}",
                            "-state",
                            str(home / "data/appstate.json"),
                            "-chain",
                            CHAIN,
                            "-balances",
                            str(home / "balances.json"),
                        ],
                        stdout=log,
                        stderr=subprocess.STDOUT,
                    )
                )

            time.sleep(2)

            # Start the four CometBFT processes.
            for i, (home, _, _) in enumerate(nodes):
                log = open(tmp / f"consensus{i}.log", "w")
                logs.append(log)

                processes.append(
                    subprocess.Popen(
                        ["cometbft", "node", "--home", str(home)],
                        stdout=log,
                        stderr=subprocess.STDOUT,
                    )
                )

            # Wait for all four validators to produce blocks.
            wait_until(
                lambda: all(
                    int(
                        rpc(
                            26657 + i * 10,
                            "status",
                        )["sync_info"]["latest_block_height"]
                    ) >= 3
                    for i in range(4)
                ),
                120,
            )

            # Sign a native transfer.
            payload = {
                "chain_id": CHAIN,
                "from": src,
                "to": dst,
                "amount": 125,
                "nonce": 0,
            }

            wire = json.dumps(
                payload,
                separators=(",", ":"),
            ).encode()

            sig = sender.sign(wire).hex()

            tx = {
                **payload,
                "public_key": pub.hex(),
                "signature": sig,
            }

            raw = json.dumps(
                tx,
                separators=(",", ":"),
            ).encode().hex()

            result = rpc(
                26657,
                "broadcast_tx_sync",
                tx="0x" + raw,
            )

            if result["code"] != 0:
                raise AssertionError(
                    f"Transaction rejected: {result}"
                )

            txhash = result["hash"]

            txinfo = wait_until(
                lambda: rpc(
                    26657,
                    "tx",
                    hash="0x" + txhash,
                    prove="false",
                ),
                90,
            )

            if txinfo["tx_result"]["code"] != 0:
                raise AssertionError(
                    f"Transaction failed: {txinfo}"
                )

            height = int(txinfo["height"])

            wait_until(
                lambda: all(
                    int(
                        rpc(
                            26657 + i * 10,
                            "status",
                        )["sync_info"]["latest_block_height"]
                    ) >= height + 2
                    for i in range(4)
                ),
                90,
            )

            # Compare application hashes at the same block height.
            hashes = [
                rpc(
                    26657 + i * 10,
                    "block",
                    height=height + 1,
                )["block"]["header"]["app_hash"]
                for i in range(4)
            ]

            if len(set(hashes)) != 1:
                raise AssertionError(
                    f"Application hashes diverged: {hashes}"
                )

            # Verify persistent account balances.
            for home, _, _ in nodes:
                state = json.loads(
                    (home / "data/appstate.json").read_text()
                )

                if (
                    state["accounts"][src]["balance"] != 875
                    or state["accounts"][dst]["balance"] != 125
                ):
                    raise AssertionError(
                        "Incorrect persisted balances"
                    )

            # Restart one consensus validator.
            processes[5].terminate()
            processes[5].wait(timeout=15)

            home = nodes[1][0]

            log = open(
                tmp / "consensus1-restart.log",
                "w",
            )
            logs.append(log)

            processes.append(
                subprocess.Popen(
                    ["cometbft", "node", "--home", str(home)],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
            )

            wait_until(
                lambda: int(
                    rpc(
                        26667,
                        "status",
                    )["sync_info"]["latest_block_height"]
                ) >= height + 3,
                90,
            )

            print(
                json.dumps(
                    {
                        "result": "PASS",
                        "chain_id": CHAIN,
                        "validators": 4,
                        "transfer": 125,
                        "tx_hash": txhash,
                        "finalized_height": height,
                        "matching_app_hash": hashes[0],
                        "validator_restart": "PASS",
                    },
                    indent=2,
                )
            )

        except Exception:
            for log in logs:
                try:
                    log.flush()
                except Exception:
                    pass

            for path in tmp.glob("*.log"):
                print(
                    f"\n===== {path.name} (last 25 lines) =====",
                    file=sys.stderr,
                )

                print(
                    "\n".join(
                        path.read_text(
                            errors="replace"
                        ).splitlines()[-25:]
                    ),
                    file=sys.stderr,
                )

            raise

        finally:
            for process in processes:
                if process.poll() is None:
                    process.terminate()

            for process in processes:
                if process.poll() is None:
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()

            for log in logs:
                log.close()


if __name__ == "__main__":
    main()
