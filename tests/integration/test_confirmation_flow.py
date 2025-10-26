import requests
import time

BASE = "http://localhost:8080"


def wait_ready(timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{BASE}/ready", timeout=2)
            if r.ok and r.json().get("ready"):
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def test_confirmation_round_trip():
    assert wait_ready(), "orchestrator not ready"

    envelope = {
        "timestamp": "2025-10-25T19:22:04Z",
        "source": "io-speech",
        "intent": "summarize.document",
        "payload": {"document_ref": "active_window", "summary_length": "short"},
        "safety_context": {"data_classification": "confidential", "allows_cloud": False},
    }

    # Issue event that should require confirmation per default rules.yaml
    r = requests.post(f"{BASE}/event", json=envelope, timeout=5)
    assert r.status_code == 200
    body = r.json()
    assert body.get("accepted") is False
    assert body.get("require_confirmation") is True
    token = body.get("confirmation_token")
    assert isinstance(token, str) and len(token) > 0

    # Confirm immediately
    r2 = requests.post(
        f"{BASE}/event/confirm",
        json={"confirmation_token": token},
        timeout=5,
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2.get("accepted") is True
    assert body2.get("handled_by") is not None
