#!/usr/bin/env python3
"""
Test multimodal I/O services (speech and vision) via Orchestrator and renderer.
"""
import os
import sys
import json
import time
from typing import Any, Dict, Tuple

import requests

ORCH = os.getenv("UNISON_ORCH_URL", "http://localhost:8080")
SPEECH = os.getenv("UNISON_SPEECH_URL", "http://localhost:8084")
VISION = os.getenv("UNISON_VISION_URL", "http://localhost:8086")
RENDERER = os.getenv("UNISON_RENDERER_URL", "http://localhost:8092")


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
    print("=== Test multimodal I/O ===")
    # Health checks
    for name, url in [("speech", f"{SPEECH}/health"), ("vision", f"{VISION}/health")]:
        ok, st, body = get_json(url)
        if not ok:
            fail(f"{name} health failed ({st})", body)
        print(f"[ok] {name} health: {st}")

    # 1) Speech STT stub
    placeholder_audio = "UklGRigAAABXQVZFZm10IBAAAAAAQAEAAEAfAAAQAQABAAgAZGF0YQQAAAA="
    ok, st, body = post_json(f"{SPEECH}/speech/stt", {"audio": placeholder_audio})
    if not ok or not isinstance(body, dict) or not body.get("ok"):
        fail("speech STT failed", body)
    transcript = body.get("transcript")
    if not isinstance(transcript, str):
        fail("speech STT missing transcript", body)
    print(f"[ok] speech STT transcript: {transcript}")

    # Send speech event via orchestrator
    env_speech = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "io-speech",
        "intent": "echo",
        "payload": {"transcript": transcript},
        "auth_scope": "person.local.explicit",
        "safety_context": {},
    }
    ok2, st2, body2 = post_json(f"{ORCH}/event", env_speech)
    if not ok2 or not isinstance(body2, dict) or not body2.get("accepted"):
        fail("orchestrator speech event failed", body2)
    outputs = body2.get("outputs", {})
    if outputs.get("transcript") != transcript:
        fail("orchestrator did not echo transcript", body2)
    print("[ok] orchestrator echoed speech transcript")

    # 2) Vision capture stub
    ok, st, body = post_json(f"{VISION}/vision/capture", {})
    if not ok or not isinstance(body, dict) or not body.get("ok"):
        fail("vision capture failed", body)
    image_url = body.get("image_url")
    if not isinstance(image_url, str) or not image_url.startswith("data:image/"):
        fail("vision capture missing image_url", body)
    print("[ok] vision capture returned data URL")

    # Send vision event via orchestrator
    env_vision = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "io-vision",
        "intent": "echo",
        "payload": {"image_url": image_url},
        "auth_scope": "person.local.explicit",
        "safety_context": {},
    }
    ok2, st2, body2 = post_json(f"{ORCH}/event", env_vision)
    if not ok2 or not isinstance(body2, dict) or not body2.get("accepted"):
        fail("orchestrator vision event failed", body2)
    outputs = body2.get("outputs", {})
    if outputs.get("image_url") != image_url:
        fail("orchestrator did not echo image_url", body2)
    print("[ok] orchestrator echoed vision image_url")

    # 3) Vision description stub (optional)
    ok, st, body = post_json(f"{VISION}/vision/describe", {"image_url": image_url})
    if not ok or not isinstance(body, dict) or not body.get("ok"):
        fail("vision describe failed", body)
    description = body.get("description")
    if not isinstance(description, str):
        fail("vision describe missing description", body)
    print(f"[ok] vision description: {description}")

    # 4) Companion voice ingest (speak -> companion.turn -> response)
    voice_payload = {
        "transcript": transcript,
        "person_id": "dev-person",
        "session_id": "dev-session",
        "wakeword_command": False,
    }
    ok3, st3, body3 = post_json(f"{ORCH}/voice/ingest", voice_payload)
    if not ok3 or not isinstance(body3, dict) or not body3.get("ok") or "result" not in body3:
        fail("companion voice ingest failed", body3)
    print("[ok] companion voice ingest produced result via /voice/ingest")

    # 5) Renderer wake-word API (dashboard/Operating Surface)
    ok4, st4, body4 = get_json(f"{RENDERER}/wakeword")
    if not ok4 or not isinstance(body4, dict) or not body4.get("wakeword"):
        fail("renderer /wakeword endpoint failed", body4)
    wakeword = body4.get("wakeword")
    print(f"[ok] renderer /wakeword reports active wake word: {wakeword!r}")

    print("=== Multimodal I/O tests completed ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
