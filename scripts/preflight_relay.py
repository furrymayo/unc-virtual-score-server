#!/usr/bin/env python3.14
"""Cloud relay pre-flight check.

Connects to ``CLOUD_RELAY_URL`` with ``CLOUD_RELAY_TOKEN`` exactly the
way the on-prem relay does, sends a single ``hello`` frame, waits a
moment to confirm the edge does not reject the connection, then exits.

Use this *before* flipping ``CLOUD_RELAY_ENABLED=1`` on prod to verify
the token, URL, and reachability without starting the polling loop.

Exit codes:
  0 — handshake accepted
  1 — config missing or unreachable
  2 — edge closed the socket (likely auth or IP allowlist)
"""
from __future__ import annotations

import json
import os
import socket
import sys
import time

PROTOCOL_VERSION = 1


def _fail(msg: str, code: int = 1) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(code)


def main() -> None:
    url = os.environ.get("CLOUD_RELAY_URL", "").strip()
    token = os.environ.get("CLOUD_RELAY_TOKEN", "")
    publisher = os.environ.get("CLOUD_RELAY_PUBLISHER_NAME", "preflight").strip() or "preflight"

    if not url:
        _fail("CLOUD_RELAY_URL is not set")
    if not token:
        _fail("CLOUD_RELAY_TOKEN is not set")

    try:
        from websocket import create_connection, WebSocketBadStatusException
    except ImportError:
        _fail("websocket-client not installed (pip install websocket-client)")

    print(f"Connecting to {url} as publisher={publisher!r}...")
    try:
        ws = create_connection(
            url,
            header=[f"X-Publisher-Auth: {token}", f"X-Publisher-Name: {publisher}"],
            timeout=10,
        )
    except WebSocketBadStatusException as exc:
        _fail(f"edge rejected connection: {exc}", code=2)
    except (socket.gaierror, ConnectionRefusedError, OSError) as exc:
        _fail(f"could not reach edge: {exc}")

    try:
        hello = {"type": "hello", "publisher": publisher, "version": PROTOCOL_VERSION}
        ws.send(json.dumps(hello))

        # If auth or IP allowlist fails, the edge closes the socket without
        # a status code. Give it a moment, then probe with a tiny ping.
        time.sleep(0.5)
        ws.send(json.dumps({"type": "ping", "ts": time.time()}))
        ws.settimeout(3.0)
        try:
            reply = ws.recv()
        except Exception as exc:
            _fail(f"edge accepted hello but closed before pong: {exc}", code=2)
        if not reply:
            _fail("edge closed the socket — likely auth or IP allowlist failure", code=2)

        try:
            msg = json.loads(reply)
        except json.JSONDecodeError:
            _fail(f"edge replied with non-JSON: {reply!r}", code=2)
        if msg.get("type") != "pong":
            _fail(f"unexpected reply: {msg!r}", code=2)
    finally:
        try:
            ws.close()
        except Exception:
            pass

    print("OK: hello accepted, pong received. Relay credentials are valid.")


if __name__ == "__main__":
    main()
