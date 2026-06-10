"""Shared fixtures for ShortCut AI Phase 2.1 tests."""
import os
import uuid
from pathlib import Path

import pytest
import requests


def _load_backend_url() -> str:
    for var in ("EXPO_PUBLIC_BACKEND_URL", "EXPO_BACKEND_URL"):
        v = os.environ.get(var)
        if v:
            return v.rstrip("/")
    # Fallback: read from frontend/.env
    env_path = Path("/app/frontend/.env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                return val.rstrip("/")
    raise RuntimeError("EXPO_PUBLIC_BACKEND_URL is not set")


BASE = _load_backend_url()

API = f"{BASE}/api/v1"


@pytest.fixture(scope="session")
def api_url():
    return API


@pytest.fixture(scope="session")
def base_url():
    return BASE


@pytest.fixture
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _signup(s, email=None, password="Demo12345!", name="Test User"):
    email = email or f"test_{uuid.uuid4().hex[:10]}@shortcut.ai"
    r = s.post(f"{API}/auth/signup", json={"email": email, "password": password, "name": name})
    return r, email, password


@pytest.fixture
def fresh_user(session):
    r, email, password = _signup(session)
    assert r.status_code == 201, f"signup failed: {r.status_code} {r.text}"
    body = r.json()
    return {
        "email": email,
        "password": password,
        "user": body["user"],
        "access_token": body["access_token"],
        "refresh_token": body["refresh_token"],
        "auth_headers": {"Authorization": f"Bearer {body['access_token']}"},
    }
