import requests
from requests.exceptions import ConnectionError

BASE = "http://localhost"


def _get(url: str):
    try:
        return requests.get(url, timeout=3)
    except ConnectionError:
        import pytest

        pytest.skip(f"Service not reachable at {url}")


def test_vpn_status_endpoint():
    resp = _get(f"{BASE}:8094/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "interface" in body
    assert "ready" in body


def test_vdi_readyz_exposes_vpn_flag():
    resp = _get(f"{BASE}:8093/readyz")
    assert resp.status_code == 200
    body = resp.json()
    assert "vpn" in body


def test_vpn_readyz_fail_when_not_ready():
    resp = _get(f"{BASE}:8094/readyz")
    if resp.status_code == 503:
        body = resp.json()
        assert body.get("ready") is False
