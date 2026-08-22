"""Probe: simulate Chrome extension WS handshake against live FBKit agent."""
from __future__ import annotations

import asyncio
import json
import sys
import urllib.error
import urllib.request

import websockets


def fetch_status() -> dict:
    with urllib.request.urlopen("http://127.0.0.1:8100/api/status", timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


async def probe() -> int:
    try:
        before = fetch_status()
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"FAIL: agent status unreachable: {exc}", file=sys.stderr)
        return 2

    print("before:", json.dumps(before.get("extension"), sort_keys=True))

    try:
        async with websockets.connect("ws://127.0.0.1:9222", open_timeout=5) as ws:
            await ws.send(
                json.dumps(
                    {
                        "type": "extension_ready",
                        "fb_uid": "test-uid-internal",
                        "loggedIn": True,
                        "extensionLiveActionsEnabled": False,
                        "profileId": "profile_internal_probe",
                        "profileName": "internal-probe",
                        "url": "https://www.facebook.com/",
                    }
                )
            )
            await asyncio.sleep(0.4)
            after = fetch_status()
    except Exception as exc:  # noqa: BLE001 — probe reports any transport failure
        print(f"FAIL: websocket probe error: {exc}", file=sys.stderr)
        return 3

    print("after:", json.dumps(after.get("extension"), sort_keys=True))
    ext = after.get("extension") or {}
    sessions = ext.get("sessions") or []
    matched = [
        s
        for s in sessions
        if s.get("fb_uid") == "test-uid-internal" and s.get("logged_in") is True
    ]
    if not ext.get("connected") and not matched:
        # Some agents mark connected only while socket open; accept match during hold.
        print("FAIL: no connected session with test fb_uid", file=sys.stderr)
        return 1
    if matched or ext.get("session_count", 0) >= 1 or ext.get("connected"):
        print("PASS: extension path accepts handshake")
        return 0
    print("FAIL: unexpected status shape", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(probe()))
