#!/usr/bin/env python3
"""
Register built-in skills with the Orchestrator.
Run after devstack is up to enable summarize.doc, context.get, and storage.put.
"""
import os
import sys
import time
from typing import Any, Dict, Tuple

import requests

ORCH = os.getenv("UNISON_ORCH_URL", "http://localhost:8080")

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

def main():
    print("=== Register built-in skills ===")
    # Wait for orchestrator to be healthy
    for i in range(10):
        ok, st, _ = get_json(f"{ORCH}/health")
        if ok:
            break
        print(f"Waiting for orchestrator... ({i+1}/10)")
        time.sleep(2)
    else:
        print("[FAIL] Orchestrator not healthy")
        sys.exit(1)

    # Register skills
    skills = ["summarize.doc", "context.get", "storage.put"]
    for intent in skills:
        ok, st, body = post_json(f"{ORCH}/skills", {"intent": intent})
        if ok:
            print(f"[ok] Registered skill: {intent}")
        else:
            print(f"[FAIL] Register {intent}: {st} {body}")
            sys.exit(1)

    # List skills
    ok, st, body = get_json(f"{ORCH}/skills")
    if ok and isinstance(body, dict):
        print(f"[info] Orchestrator skills: {body.get('skills', [])}")
    else:
        print("[WARN] Could not list skills")
    print("=== Skill registration complete ===")

if __name__ == "__main__":
    sys.exit(main())
