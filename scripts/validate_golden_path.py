#!/usr/bin/env python3
"""
Validate the current renderer-led golden path shape for local devstack.

This is intentionally lightweight. It validates the current Milestone 1 anchors
that already exist across services:
- orchestrator startup readiness shape
- renderer onboarding aggregation shape
- orchestrator briefing path via dashboard.refresh
- orchestrator voice ingest path

It is not a replacement for platform install acceptance.
"""
import json
import os
import sys
import time
from typing import Any, Dict, Tuple

import requests

ORCH = os.getenv("UNISON_ORCH_URL", "http://localhost:8080")
RENDERER = os.getenv("UNISON_RENDERER_URL", "http://localhost:8092")
PERSON_ID = os.getenv("UNISON_PERSON_ID", "local-person")
SESSION_ID = os.getenv("UNISON_SESSION_ID", "golden-path-session")
BEARER_TOKEN = os.getenv("UNISON_BEARER_TOKEN", "")


def _headers(url: str) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if BEARER_TOKEN and (url.startswith(ORCH) or url.startswith(RENDERER)):
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
    print("=== Validate renderer-led golden path ===")

    ok, st, startup = get_json(f"{ORCH}/startup/status")
    if not ok or not isinstance(startup, dict):
        fail(f"startup/status failed ({st})", startup)
    required_startup_keys = {"state", "onboarding_required", "bootstrap_required", "renderer_ready", "core_ready", "speech_ready"}
    missing = sorted(required_startup_keys - set(startup.keys()))
    if missing:
        fail("startup/status missing required keys", {"missing": missing, "body": startup})
    print(f"[ok] startup/status shape valid ({startup.get('state')})")

    ok, st, onboarding = get_json(f"{RENDERER}/onboarding-status?person_id={PERSON_ID}")
    if not ok or not isinstance(onboarding, dict):
        fail(f"renderer onboarding-status failed ({st})", onboarding)
    required_onboarding_keys = {"person_id", "startup", "steps", "blocked_steps", "remediation", "ready_to_finish"}
    missing = sorted(required_onboarding_keys - set(onboarding.keys()))
    if missing:
        fail("onboarding-status missing required keys", {"missing": missing, "body": onboarding})
    print(f"[ok] onboarding-status shape valid (ready_to_finish={onboarding.get('ready_to_finish')})")

    briefing_env = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "golden-path-validator",
        "intent": "dashboard.refresh",
        "payload": {"person_id": PERSON_ID},
    }
    ok, st, briefing = post_json(f"{ORCH}/event", briefing_env)
    if not ok or not isinstance(briefing, dict) or not briefing.get("ok"):
        fail(f"dashboard.refresh failed ({st})", briefing)
    result = briefing.get("result") or {}
    cards = result.get("cards") if isinstance(result, dict) else None
    if not isinstance(cards, list):
        fail("dashboard.refresh did not return cards", briefing)
    print(f"[ok] dashboard.refresh returned {len(cards)} cards")

    voice_payload = {
        "transcript": "give me a short system summary",
        "person_id": PERSON_ID,
        "session_id": SESSION_ID,
        "wakeword_command": False,
    }
    ok, st, voice = post_json(f"{ORCH}/voice/ingest", voice_payload)
    if not ok or not isinstance(voice, dict) or not voice.get("ok") or "result" not in voice:
        fail(f"voice/ingest failed ({st})", voice)
    print("[ok] voice/ingest returned a companion result")

    print("=== Golden path validation completed ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
