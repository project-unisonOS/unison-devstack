import os
import requests
import time

BASE = os.getenv("UNISON_BASE", "http://localhost")


def wait_ready(url: str, timeout_s: int = 20):
    start = time.time()
    while time.time() - start < timeout_s:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200 and r.json().get("ready") is True:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def test_ready_flow():
    assert wait_ready(f"{BASE}:8080/ready"), "orchestrator not ready in time"


def test_event_happy_path():
    payload = {
        "timestamp": "2025-10-25T19:22:04Z",
        "source": "io-speech",
        "intent": "summarize.document",
        "payload": {"document_ref": "active_window", "summary_length": "short"},
        "auth_scope": "person.local.explicit",
        "safety_context": {"data_classification": "internal", "allows_cloud": False},
    }
    r = requests.post(f"{BASE}:8080/event", json=payload, timeout=3)
    assert r.status_code == 200
    j = r.json()
    assert j.get("accepted") is True
