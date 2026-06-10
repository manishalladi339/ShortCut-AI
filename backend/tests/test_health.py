"""Health endpoints."""
import requests


def test_root_health(api_url):
    r = requests.get(f"{api_url}/health", timeout=10)
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_api_root(base_url):
    r = requests.get(f"{base_url}/api/", timeout=10)
    assert r.status_code == 200
    assert "ShortCut" in r.json().get("name", "")
