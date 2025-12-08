import requests

BASE = "http://localhost"


def test_vpn_status_endpoint():
    resp = requests.get(f"{BASE}:8094/status", timeout=3)
    assert resp.status_code == 200
    body = resp.json()
    assert "interface" in body
    assert "ready" in body


def test_vdi_readyz_exposes_vpn_flag():
    resp = requests.get(f"{BASE}:8093/readyz", timeout=3)
    assert resp.status_code == 200
    body = resp.json()
    assert "vpn" in body
