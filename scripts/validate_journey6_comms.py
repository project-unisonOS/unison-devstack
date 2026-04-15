#!/usr/bin/env python3
"""
Validate the current bounded Journey 6 Gmail path for local devstack.

This validator is intentionally opt-in and only runs when explicit Gmail test
credentials are supplied. It exercises the currently implemented unison-comms
surface without pretending OAuth/device flow is done.
"""
import json
import os
import sys
from typing import Any, Dict, Tuple

import requests

COMMS = os.getenv("UNISON_COMMS_URL", "http://localhost:8088")
PERSON_ID = os.getenv("UNISON_PERSON_ID", "local-user")
BEARER_TOKEN = os.getenv("UNISON_BEARER_TOKEN", "")
GMAIL_BOOTSTRAP_USERNAME = os.getenv("UNISON_TEST_GMAIL_USERNAME", "")
GMAIL_BOOTSTRAP_APP_PASSWORD = os.getenv("UNISON_TEST_GMAIL_APP_PASSWORD", "")


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
    print("=== Validate Journey 6 bounded Gmail path ===")

    if not GMAIL_BOOTSTRAP_USERNAME or not GMAIL_BOOTSTRAP_APP_PASSWORD:
        print("[skip] set UNISON_TEST_GMAIL_USERNAME and UNISON_TEST_GMAIL_APP_PASSWORD to run this validator")
        return 0

    ok, st, body = get_json(f"{COMMS}/comms/onboarding/email")
    if not ok or not isinstance(body, dict) or not body.get("ok"):
        fail(f"email onboarding state failed ({st})", body)
    print(f"[ok] onboarding state available (state={body.get('state')}, source={body.get('credential_source')})")

    bootstrap_body = {
        "provider": "gmail",
        "username": GMAIL_BOOTSTRAP_USERNAME,
        "app_password": GMAIL_BOOTSTRAP_APP_PASSWORD,
    }
    ok, st, body = post_json(f"{COMMS}/comms/onboarding/email/bootstrap", bootstrap_body)
    if not ok or not isinstance(body, dict) or not body.get("ok"):
        fail(f"gmail bootstrap failed ({st})", body)
    print("[ok] gmail bootstrap accepted")

    ok, st, body = post_json(f"{COMMS}/comms/onboarding/email/verify", {})
    if not ok or not isinstance(body, dict) or body.get("provider") != "gmail":
        fail(f"gmail verify failed ({st})", body)
    if body.get("status") not in {"verified", "verification_failed", "needs_configuration"}:
        fail("gmail verify returned unexpected status", body)
    print(f"[ok] gmail verify returned bounded status: {body.get('status')}")

    ok, st, body = post_json(
        f"{COMMS}/comms/summarize",
        {"person_id": PERSON_ID, "window": "today", "channel": "email"},
    )
    if not ok or not isinstance(body, dict) or body.get("provider") != "gmail":
        fail(f"gmail summarize failed ({st})", body)
    required = {"status", "message_count", "summary"}
    missing = sorted(required - set(body.keys()))
    if missing:
        fail("gmail summarize missing required fields", {"missing": missing, "body": body})
    print(f"[ok] gmail summarize returned status={body.get('status')} count={body.get('message_count')}")

    ok, st, body = post_json(f"{COMMS}/comms/onboarding/email/reset", {})
    if not ok or not isinstance(body, dict) or not body.get("ok"):
        fail(f"gmail reset failed ({st})", body)
    print(f"[ok] gmail reset returned cleared_bootstrap_store={body.get('cleared_bootstrap_store')}")

    print("=== Journey 6 bounded Gmail validation completed ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
