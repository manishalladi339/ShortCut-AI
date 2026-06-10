"""Project CRUD + quota tests."""
import uuid

import requests


def _project_payload(title="TEST_Project"):
    return {
        "title": title,
        "description": "desc",
        "content_type": "podcast",
        "creation_mode": "create_for_me",
        "desired_style": "cinematic",
        "target_platforms": ["ig_reels", "yt_shorts"],
        "prompt": "make it good",
    }


def test_create_get_update_archive_delete_flow(api_url, session, fresh_user):
    h = fresh_user["auth_headers"]
    # Create
    r = session.post(f"{api_url}/projects", json=_project_payload("TEST_Flow"), headers=h)
    assert r.status_code == 201, r.text
    proj = r.json()
    pid = proj["id"]
    assert proj["title"] == "TEST_Flow"
    assert proj["status"] == "draft"
    assert proj["archived"] is False
    assert proj["target_platforms"] == ["ig_reels", "yt_shorts"]

    # GET by id
    r = session.get(f"{api_url}/projects/{pid}", headers=h)
    assert r.status_code == 200
    assert r.json()["id"] == pid

    # PATCH
    r = session.patch(f"{api_url}/projects/{pid}", json={"title": "TEST_Updated"}, headers=h)
    assert r.status_code == 200
    assert r.json()["title"] == "TEST_Updated"

    # GET to verify persistence
    r = session.get(f"{api_url}/projects/{pid}", headers=h)
    assert r.json()["title"] == "TEST_Updated"

    # Duplicate
    r = session.post(f"{api_url}/projects/{pid}/duplicate", headers=h)
    assert r.status_code == 201, r.text
    dup = r.json()
    assert dup["id"] != pid
    assert dup["title"].endswith("(Copy)")

    # Archive
    r = session.post(f"{api_url}/projects/{pid}/archive", headers=h)
    assert r.status_code == 200
    assert r.json()["archived"] is True
    assert r.json()["status"] == "archived"

    # List archived
    r = session.get(f"{api_url}/projects?archived=true", headers=h)
    assert r.status_code == 200
    archived_ids = [p["id"] for p in r.json()["items"]]
    assert pid in archived_ids

    # Delete
    r = session.delete(f"{api_url}/projects/{pid}", headers=h)
    assert r.status_code == 200
    # Confirm gone
    r = session.get(f"{api_url}/projects/{pid}", headers=h)
    assert r.status_code == 404


def test_cross_user_isolation_returns_404(api_url, session, fresh_user):
    # User A creates project
    r = session.post(f"{api_url}/projects", json=_project_payload("TEST_UserA"), headers=fresh_user["auth_headers"])
    assert r.status_code == 201
    pid = r.json()["id"]

    # User B signs up
    email_b = f"userb_{uuid.uuid4().hex[:8]}@shortcut.ai"
    rb = session.post(f"{api_url}/auth/signup", json={"email": email_b, "password": "Demo12345!", "name": "B"})
    assert rb.status_code == 201
    hb = {"Authorization": f"Bearer {rb.json()['access_token']}"}

    # B tries to GET A's project
    r = session.get(f"{api_url}/projects/{pid}", headers=hb)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "resource.not_found"

    # B tries PATCH
    r = session.patch(f"{api_url}/projects/{pid}", json={"title": "hack"}, headers=hb)
    assert r.status_code == 404

    # B tries DELETE
    r = session.delete(f"{api_url}/projects/{pid}", headers=hb)
    assert r.status_code == 404


def test_recent_and_continue_editing(api_url, session, fresh_user):
    h = fresh_user["auth_headers"]
    r = session.post(f"{api_url}/projects", json=_project_payload("TEST_Recent1"), headers=h)
    assert r.status_code == 201
    pid = r.json()["id"]

    r = session.get(f"{api_url}/projects/recent", headers=h)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert any(p["id"] == pid for p in r.json())

    r = session.get(f"{api_url}/projects/continue-editing", headers=h)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    # New project status=draft so should appear
    assert any(p["id"] == pid for p in r.json())


def test_projects_require_auth(api_url, session):
    r = session.get(f"{api_url}/projects")
    assert r.status_code == 401
    r = session.post(f"{api_url}/projects", json=_project_payload())
    assert r.status_code == 401


def test_free_tier_quota_4th_project_402(api_url, session, fresh_user):
    h = fresh_user["auth_headers"]
    # Create 3 successful projects
    for i in range(3):
        r = session.post(f"{api_url}/projects", json=_project_payload(f"TEST_Quota_{i}"), headers=h)
        assert r.status_code == 201, f"project {i}: {r.status_code} {r.text}"
    # 4th must fail with 402
    r = session.post(f"{api_url}/projects", json=_project_payload("TEST_Quota_4"), headers=h)
    assert r.status_code == 402, f"expected 402 got {r.status_code} {r.text}"
    assert r.json()["error"]["code"] == "quota.exceeded"
