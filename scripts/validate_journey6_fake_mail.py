#!/usr/bin/env python3
"""
Validate a local fake-mail Journey 6 path without external credentials.

This validator uses the existing stubbed email path in unison-comms to prove the
bounded onboarding/check/summarize/compose contract at a devstack level without
requiring real Gmail credentials.
"""
import json
import os
import sys
from typing import Any, Dict, Tuple

import requests

COMMS = os.getenv("UNISON_COMMS_URL", "http://localhost:8088")
PERSON_ID = os.getenv("UNISON_PERSON_ID", "local-user")
BEARER_TOKEN = os.getenv("UNISON_BEARER_TOKEN", "")


def _headers(url: str) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if BEARER_TOKEN and url.startswith(COMMS):
        headers["Authorization"] = f"Bearer {BEARER_TOKEN}"
    return headers


def get_json(url: str) -> Tuple[bool, int, Any]:
    try:
        r = requests.get(url, headers=_headers(url), timeout=5)
        try:
            data = r.json()
        except Exception:
            data = r.text
        return r.ok, r.status_code, data
    except Exception as e:
        return False, 0, str(e)


def post_json(url: str, body: Dict[str, Any]) -> Tuple[bool, int, Any]:
    try:
        r = requests.post(url, json=body, headers=_headers(url), timeout=8)
        try:
            data = r.json()
        except Exception:
            data = r.text
        return r.ok, r.status_code, data
    except Exception as e:
        return False, 0, str(e)


def fail(msg: str, payload: Any = None) -> None:
    print(f"[FAIL] {msg}")
    if payload is not None:
        try:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        except Exception:
            print(payload)
    sys.exit(1)


def main() -> int:
    print("=== Validate Journey 6 fake-mail path ===")

    ok, st, body = get_json(f"{COMMS}/readyz")
    if not ok or not isinstance(body, dict):
        fail(f"comms readyz failed ({st})", body)
    print(f"[ok] comms readyz status={body.get('status')}")

    ok, st, body = get_json(f"{COMMS}/comms/onboarding/email")
    if not ok or not isinstance(body, dict) or not body.get("ok"):
        fail(f"email onboarding state failed ({st})", body)
    print(f"[ok] onboarding state available (provider={body.get('provider')}, state={body.get('state')})")

    ok, st, body = post_json(f"{COMMS}/comms/check", {"person_id": PERSON_ID, "channel": "email"})
    if not ok or not isinstance(body, dict) or not body.get("ok"):
        fail(f"fake-mail check failed ({st})", body)
    if body.get("status") not in {"messages_found", "no_messages"}:
        fail("fake-mail check returned unexpected status", body)
    print(f"[ok] fake-mail check status={body.get('status')} count={body.get('message_count')}")

    ok, st, body = post_json(f"{COMMS}/comms/summarize", {"person_id": PERSON_ID, "window": "today", "channel": "email"})
    if not ok or not isinstance(body, dict) or not body.get("ok"):
        fail(f"fake-mail summarize failed ({st})", body)
    required = {"status", "message_count", "summary", "provider"}
    missing = sorted(required - set(body.keys()))
    if missing:
        fail("fake-mail summarize missing required fields", {"missing": missing, "body": body})
    print(f"[ok] fake-mail summarize status={body.get('status')} count={body.get('message_count')}")

    compose_body = {
        "person_id": PERSON_ID,
        "channel": "email",
        "recipients": ["test@example.com"],
        "subject": "Journey 6 fake-mail validation",
        "body": "This is a bounded fake-mail validation message.",
    }
    ok, st, body = post_json(f"{COMMS}/comms/compose", compose_body)
    if not ok or not isinstance(body, dict) or not body.get("ok"):
        fail(f"fake-mail compose failed ({st})", body)
    if body.get("origin_intent") != "comms.compose":
        fail("fake-mail compose returned unexpected shape", body)
    print(f"[ok] fake-mail compose status={body.get('status')}")

    ok, st, body = post_json(f"{COMMS}/comms/check", {"person_id": PERSON_ID, "channel": "email"})
    if not ok or not isinstance(body, dict) or not body.get("ok"):
        fail(f"fake-mail re-check failed ({st})", body)
    msgs = body.get("messages") or []
    if not any(isinstance(m, dict) and m.get("subject") == "Journey 6 fake-mail validation" for m in msgs):
        fail("fake-mail re-check did not return composed message", body)
    print("[ok] fake-mail re-check returned composed message")

    print("=== Journey 6 fake-mail validation completed ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
