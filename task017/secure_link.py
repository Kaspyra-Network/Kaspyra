"""Mutually authenticated TLS forwarding for the Task 016 loopback field harness.

The listener accepts one TLS connection and forwards one framed request/response
exchange to the Task 016 receiver on localhost. No plaintext public listener.
"""
import argparse
import json
import socket
import ssl
import threading
import time

MAX_BYTES = 1024 * 1024


def pipe(src, dst):
    try:
        while True:
            chunk = src.recv(65536)
            if not chunk:
                try: dst.shutdown(socket.SHUT_WR)
                except OSError: pass
                break
            dst.sendall(chunk)
    except (OSError, ssl.SSLError):
        pass


def bridge(incoming, upstream_host, upstream_port):
    with incoming:
        with socket.create_connection((upstream_host, upstream_port), timeout=10) as upstream:
            incoming.settimeout(30)
            upstream.settimeout(30)
            worker = threading.Thread(target=pipe, args=(incoming, upstream), daemon=True)
            worker.start()
            pipe(upstream, incoming)
            worker.join(timeout=2)


def contexts(ca, cert, key, server=False):
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH if server else ssl.Purpose.SERVER_AUTH, cafile=ca)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(cert, key)
    if server:
        ctx.verify_mode = ssl.CERT_REQUIRED
    return ctx


def serve(bind_host, bind_port, upstream_host, upstream_port, ca, cert, key, limit=0):
    if upstream_host not in ('127.0.0.1', '::1', 'localhost'):
        raise ValueError('upstream must be local loopback')
    ctx = contexts(ca, cert, key, server=True)
    count = 0
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((bind_host, bind_port))
        listener.listen(16)
        print(json.dumps({'event':'ready','address':listener.getsockname(), 'satellite_verified':False}), flush=True)
        while not limit or count < limit:
            raw, _ = listener.accept()
            try:
                tls = ctx.wrap_socket(raw, server_side=True)
            except ssl.SSLError:
                raw.close()
                continue
            count += 1
            threading.Thread(target=bridge, args=(tls, upstream_host, upstream_port), daemon=True).start()


def client(bind_host, bind_port, remote_host, remote_port, ca, cert, key, server_name, limit=0):
    ctx = contexts(ca, cert, key)
    count = 0
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((bind_host, bind_port))
        listener.listen(16)
        print(json.dumps({'event':'ready','address':listener.getsockname(), 'satellite_verified':False}), flush=True)
        while not limit or count < limit:
            local, _ = listener.accept()
            try:
                raw = socket.create_connection((remote_host, remote_port), timeout=10)
                tls = ctx.wrap_socket(raw, server_hostname=server_name)
            except (OSError, ssl.SSLError):
                local.close()
                continue
            count += 1
            threading.Thread(target=bridge_client, args=(local, tls), daemon=True).start()


def bridge_client(local, tls):
    with local, tls:
        local.settimeout(30)
        tls.settimeout(30)
        worker = threading.Thread(target=pipe, args=(local, tls), daemon=True)
        worker.start()
        pipe(tls, local)
        worker.join(timeout=2)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='mode', required=True)
    for mode in ('server','client'):
        s = sub.add_parser(mode)
        s.add_argument('--bind', default='127.0.0.1')
        s.add_argument('--port', type=int, required=True)
        s.add_argument('--ca', required=True)
        s.add_argument('--cert', required=True)
        s.add_argument('--key', required=True)
        s.add_argument('--limit', type=int, default=0)
    s = sub.choices['server']; s.add_argument('--upstream-host', default='127.0.0.1'); s.add_argument('--upstream-port', type=int, default=18716)
    c = sub.choices['client']; c.add_argument('--remote-host', required=True); c.add_argument('--remote-port', type=int, required=True); c.add_argument('--server-name', required=True)
    a = p.parse_args()
    if a.mode == 'server': serve(a.bind,a.port,a.upstream_host,a.upstream_port,a.ca,a.cert,a.key,a.limit)
    else: client(a.bind,a.port,a.remote_host,a.remote_port,a.ca,a.cert,a.key,a.server_name,a.limit)

if __name__ == '__main__': main()
