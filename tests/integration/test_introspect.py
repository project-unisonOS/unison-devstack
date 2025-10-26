import requests
import time

BASE = "http://localhost:8080"


def wait_ready(timeout=15):
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


def test_introspect_endpoint():
    assert wait_ready(), "orchestrator not ready"
    r = requests.get(f"{BASE}/introspect", timeout=5)
    assert r.status_code == 200
    body = r.json()
    assert "services" in body
    assert "skills" in body
    assert "policy_rules" in body
