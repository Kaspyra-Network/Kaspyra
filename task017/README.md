# Task 017 — Two-machine authenticated remote link (pre-deployment)

This adds a mutual-TLS forwarding option for the existing Task 016 field-link harness. It does **not** deploy servers, provision certificates, establish satellite connectivity, or prove a satellite path.

## Prerequisites

- Two independently operated machines with Python 3.11+, and TCP reachability from A to B.
- Task 016 receiver and sender available on the respective machines.
- A private CA and **separate** client/server certificates and private keys, with server DNS/IP SAN matching `--server-name`. Never commit private keys or certificates to GitHub.
- Network firewall allowing the TLS port on B **only from A**; Task 016 receiver binds to 127.0.0.1 only.
- Certificate lifecycle/revocation and OS hardening are required before persistent public deployment.

## Receiver B

Start Task 016 receiver bound to `127.0.0.1:18716`. Then:

```bash
python task017/secure_link.py server --bind 0.0.0.0 --port 18717 --upstream-host 127.0.0.1 --upstream-port 18716 --ca /secure/ca.pem --cert /secure/server.pem --key /secure/server.key
```

## Sender A

```bash
python task017/secure_link.py client --bind 127.0.0.1 --port 18718 --remote-host RECEIVER_IP --remote-port 18717 --server-name RECEIVER_CERT_DNS --ca /secure/ca.pem --cert /secure/client.pem --key /secure/client.key
python task016/field_link.py transmit sender.db --host 127.0.0.1 --port 18718
```

Queue a signed message using the Task 016 instructions before transmitting. Verify accepted response and inbox database on B. Do not expose Task 016 plaintext ports publicly. Use a trusted isolated network first.

## Acceptance evidence

Record independently: host identifiers (not secrets), network interface and provider, sender and receiver logs, envelope hash, TLS peer verification, RTT, packet counters, outage/retry evidence, and successful transaction inclusion when a local blockchain RPC is present. Public traceroute alone does not prove satellite-only routing; require provider documentation.

## Limitations

This is a prototype forwarder. It is not a production-grade daemon, a satellite implementation, a CometBFT P2P transport replacement, or a verified remote deployment. The CI tests validate TLS configuration and guardrails, **not** actual two-host connectivity.
