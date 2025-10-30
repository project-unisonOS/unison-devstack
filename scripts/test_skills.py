#!/usr/bin/env python3
"""
Test registered skills: summarize.doc, context.get, storage.put.
"""
import os
import sys
import json
import time
from typing import Any, Dict, Tuple

import requests

ORCH = os.getenv("UNISON_ORCH_URL", "http://localhost:8080")
CTX = os.getenv("UNISON_CONTEXT_URL", "http://localhost:8081")
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
    print("=== Test registered skills ===")
    # Ensure skills are registered
    ok, st, body = get_json(f"{ORCH}/skills")
    if not ok or not isinstance(body, dict):
        fail("Could not list skills", body)
    skills = body.get("skills", [])
    expected = {"summarize.doc", "context.get", "storage.put"}
    missing = expected - set(skills)
    if missing:
        fail(f"Skills not registered: {missing}")
    print(f"[ok] Skills registered: {skills}")

    # 1) summarize.doc (policy may require confirmation; we accept either)
    env = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "test-skills",
        "intent": "summarize.doc",
        "payload": {"document_ref": "test.txt"},
        "safety_context": {"data_classification": "internal"},
    }
    ok, st, body = post_json(f"{ORCH}/event", env)
    if not isinstance(body, dict):
        fail("summarize.doc /event bad response", body)
    if body.get("require_confirmation") is True and body.get("confirmation_token"):
        token = body.get("confirmation_token")
        ok2, st2, conf = post_json(f"{ORCH}/event/confirm", {"confirmation_token": token})
        if not ok2 or not isinstance(conf, dict) or not conf.get("accepted"):
            fail("summarize.doc confirmation failed", conf)
        print("[ok] summarize.doc executed via confirmation")
    elif body.get("accepted"):
        print("[ok] summarize.doc executed directly")
    else:
        fail("summarize.doc not accepted", body)

    # 2) context.get
    # First, store a key via Context KV
    ok_put, st_put, body_put = post_json(f"{CTX}/kv/put", {
        "person_id": PERSON_ID,
        "tier": "B",
        "items": {f"{PERSON_ID}:test:skill": "value_from_skill_test"}
    })
    if not ok_put or not isinstance(body_put, dict) or not body_put.get("ok"):
        fail("context kv/put failed", body_put)
    # Now call via skill
    env2 = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "test-skills",
        "intent": "context.get",
        "payload": {"keys": [f"{PERSON_ID}:test:skill"]},
    }
    ok2, st2, body2 = post_json(f"{ORCH}/event", env2)
    if not ok2 or not isinstance(body2, dict) or not body2.get("accepted"):
        fail("context.get /event failed", body2)
    outputs = body2.get("outputs", {})
    if f"{PERSON_ID}:test:skill" not in outputs.get("values", {}):
        fail("context.get missing expected key", body2)
    print("[ok] context.get returned stored value")

    # 3) storage.put
    env3 = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "test-skills",
        "intent": "storage.put",
        "payload": {"namespace": "test", "key": "skill_example", "value": {"hello": "world"}},
    }
    ok3, st3, body3 = post_json(f"{ORCH}/event", env3)
    if not ok3 or not isinstance(body3, dict) or not body3.get("accepted"):
        fail("storage.put /event failed", body3)
    print("[ok] storage.put executed")

    print("=== Skill tests completed ===")
    return 0

if __name__ == "__main__":
    sys.exit(main())
