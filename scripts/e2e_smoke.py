#!/usr/bin/env python3
import os
import sys
import json
import time
from typing import Any, Dict, Tuple

import requests

ORCH = os.getenv("UNISON_ORCH_URL", "http://localhost:8080")
CTX = os.getenv("UNISON_CONTEXT_URL", "http://localhost:8081")
IOCORE = os.getenv("UNISON_IOCORE_URL", "http://localhost:8085")
POLICY = os.getenv("UNISON_POLICY_URL", "http://localhost:8083")
ACT = os.getenv("UNISON_ACTUATION_URL", "http://localhost:8096")

PERSON_ID = os.getenv("UNISON_PERSON_ID", "local-user")


def post_json(url: str, body: Dict[str, Any]) -> Tuple[bool, int, Any]:
    try:
        r = requests.post(url, json=body, timeout=5)
        try:
            data = r.json()
        except Exception:
            data = r.text
        return (r.ok, r.status_code, data)
    except Exception as e:
        return (False, 0, str(e))


def get_json(url: str) -> Tuple[bool, int, Any]:
    try:
        r = requests.get(url, timeout=5)
        try:
            data = r.json()
        except Exception:
            data = r.text
        return (r.ok, r.status_code, data)
    except Exception as e:
        return (False, 0, str(e))


def fail(msg: str, payload: Any = None):
    print(f"[FAIL] {msg}")
    if payload is not None:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    sys.exit(1)


def main():
    print("=== E2E smoke: Developer Mode ===")

    # Health checks
    for name, url in [
        ("orchestrator", f"{ORCH}/health"),
        ("context", f"{CTX}/health"),
        ("policy", f"{POLICY}/health"),
        ("actuation", f"{ACT}/health"),
        ("io-core", f"{IOCORE}/health"),
    ]:
        ok, st, body = get_json(url)
        if not ok:
            fail(f"{name} health failed ({st})", body)
        print(f"[ok] {name} health: {st}")

    # 1) Onboarding save (Tier B)
    kv_put = {
        "person_id": PERSON_ID,
        "tier": "B",
        "items": {
            f"{PERSON_ID}:profile:language": "en",
            f"{PERSON_ID}:profile:onboarding_complete": True,
        },
    }
    ok, st, body = post_json(f"{CTX}/kv/put", kv_put)
    if not ok or not isinstance(body, dict) or not body.get("ok"):
        fail("context kv/put failed", body)
    print("[ok] context kv/put")

    # 2) Profile export
    ok, st, body = post_json(f"{CTX}/profile.export", {"person_id": PERSON_ID})
    if not ok or not isinstance(body, dict) or not body.get("ok"):
        fail("context profile.export failed", body)
    items = body.get("items") or {}
    if f"{PERSON_ID}:profile:language" not in items:
        fail("export missing expected key", body)
    print("[ok] context profile.export contains Tier B keys")

    # 3) Echo via io-core
    envelope = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "e2e-script",
        "intent": "echo",
        "payload": {"message": "hello from e2e"},
    }
    ok, st, body = post_json(f"{IOCORE}/io/emit", envelope)
    if not ok or not isinstance(body, dict) or not body.get("ok"):
        fail("io-core emit failed", body)
    print("[ok] io-core -> orchestrator echo")

    # 4) Policy require_confirmation path via orchestrator
    env2 = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "e2e-script",
        "intent": "summarize.doc",
        "payload": {},
        "safety_context": {"data_classification": "confidential"},
    }
    ok, st, body = post_json(f"{ORCH}/event", env2)
    if not isinstance(body, dict):
        fail("orchestrator /event bad response", body)
    if body.get("require_confirmation") is True and not body.get("accepted"):
        token = body.get("confirmation_token")
        if not isinstance(token, str):
            fail("missing confirmation token", body)
        ok2, st2, conf = post_json(f"{ORCH}/event/confirm", {"confirmation_token": token})
        if not ok2 or not isinstance(conf, dict) or not conf.get("accepted"):
            fail("confirmation failed", conf)
        print("[ok] orchestrator confirmation path executed")
    else:
        # Either allowed or denied without confirmation; still acceptable
        print("[ok] orchestrator policy path (no confirmation required)")

    # 5) Proposed action -> actuation (logging/mock)
    act_env = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "e2e-script",
        "intent": "proposed_action",
        "payload": {
            "person_id": PERSON_ID,
            "target": {"device_id": "light-1", "device_class": "light"},
            "intent": {"name": "turn_on", "parameters": {"level": 50}},
            "risk_level": "low",
            "telemetry_channel": {"topic": "devstack.e2e"},
        },
    }
    ok, st, body = post_json(f"{ORCH}/event", act_env)
    if not ok or not isinstance(body, dict) or not body.get("ok"):
        fail("proposed_action flow failed", body)
    act_res = body.get("result") or body.get("actuation_result") or body.get("body") or body.get("result", {})
    if isinstance(act_res, dict):
        print(f"[ok] actuation response status: {act_res.get('status')}")
    else:
        print("[ok] actuation response (non-dict)")
    ok, st, telem = get_json(f"{ACT}/telemetry/recent")
    if not ok or not isinstance(telem, list):
        fail("actuation telemetry retrieval failed", telem)
    if telem:
        print(f"[ok] telemetry entries: {len(telem)} (latest status={telem[-1].get('status')})")
    else:
        print("[warn] no telemetry entries returned")

    print("=== E2E smoke completed ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
