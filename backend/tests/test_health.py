"""Health, readiness and request-tracing endpoints."""
import uuid

import requests


def test_root_health(api_url):
    r = requests.get(f"{api_url}/health", timeout=10)
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_liveness_endpoint(api_url):
    r = requests.get(f"{api_url}/live", timeout=10)
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_readiness_checks_dependencies(api_url):
    r = requests.get(f"{api_url}/ready", timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["checks"]["mongo"]["ok"] is True
    assert body["checks"]["storage"]["ok"] is True


def test_request_id_round_trip(api_url):
    request_id = f"test-{uuid.uuid4()}"
    r = requests.get(
        f"{api_url}/live",
        headers={"X-Request-ID": request_id},
        timeout=10,
    )
    assert r.status_code == 200
    assert r.headers["X-Request-ID"] == request_id


def test_api_root(base_url):
    r = requests.get(f"{base_url}/api/", timeout=10)
    assert r.status_code == 200
    assert "ShortCut" in r.json().get("name", "")
