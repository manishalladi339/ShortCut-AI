"""Tests for canonical ProjectState and optimistic editing operations."""


def _project_payload():
    return {
        "title": "TEST_State",
        "content_type": "podcast",
        "creation_mode": "create_with_me",
        "target_platforms": ["ig_reels"],
    }


def test_state_initializes_for_owned_project(api_url, session, fresh_user):
    headers = fresh_user["auth_headers"]
    project = session.post(f"{api_url}/projects", json=_project_payload(), headers=headers).json()

    response = session.get(f"{api_url}/projects/{project['id']}/state", headers=headers)
    assert response.status_code == 200, response.text
    state = response.json()
    assert state["project_id"] == project["id"]
    assert state["version"] == 1
    assert state["active_sequence_id"] == state["sequences"][0]["id"]
    assert {track["kind"] for track in state["sequences"][0]["tracks"]} == {
        "video",
        "audio",
        "caption",
    }


def test_operation_increments_version_and_rejects_stale_write(api_url, session, fresh_user):
    headers = fresh_user["auth_headers"]
    project = session.post(f"{api_url}/projects", json=_project_payload(), headers=headers).json()
    state = session.get(f"{api_url}/projects/{project['id']}/state", headers=headers).json()
    sequence_id = state["active_sequence_id"]

    response = session.post(
        f"{api_url}/projects/{project['id']}/operations",
        headers=headers,
        json={
            "expected_version": 1,
            "operation": "rename_sequence",
            "payload": {"sequence_id": sequence_id, "name": "Vertical Reel"},
        },
    )
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["version"] == 2
    assert updated["sequences"][0]["name"] == "Vertical Reel"

    stale = session.post(
        f"{api_url}/projects/{project['id']}/operations",
        headers=headers,
        json={
            "expected_version": 1,
            "operation": "rename_sequence",
            "payload": {"sequence_id": sequence_id, "name": "Stale"},
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "project_state.version_conflict"


def test_state_is_private_to_project_owner(api_url, session, fresh_user):
    import uuid

    headers = fresh_user["auth_headers"]
    project = session.post(f"{api_url}/projects", json=_project_payload(), headers=headers).json()

    signup = session.post(
        f"{api_url}/auth/signup",
        json={
            "email": f"state_{uuid.uuid4().hex[:8]}@shortcut.ai",
            "password": "Demo12345!",
            "name": "Other",
        },
    )
    other_headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
    response = session.get(f"{api_url}/projects/{project['id']}/state", headers=other_headers)
    assert response.status_code == 404
