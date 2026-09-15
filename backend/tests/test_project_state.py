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


def test_track_edit_operations(api_url, session, fresh_user):
    headers = fresh_user["auth_headers"]
    project = session.post(
        f"{api_url}/projects", json=_project_payload(), headers=headers
    ).json()
    state = session.get(
        f"{api_url}/projects/{project['id']}/state", headers=headers
    ).json()
    sequence_id = state["active_sequence_id"]

    added = session.post(
        f"{api_url}/projects/{project['id']}/operations",
        headers=headers,
        json={
            "expected_version": state["version"],
            "operation": "add_track",
            "payload": {
                "sequence_id": sequence_id,
                "kind": "overlay",
                "name": "B-roll",
            },
        },
    )
    assert added.status_code == 200, added.text
    state = added.json()
    track = next(t for t in state["sequences"][0]["tracks"] if t["name"] == "B-roll")

    configured = session.post(
        f"{api_url}/projects/{project['id']}/operations",
        headers=headers,
        json={
            "expected_version": state["version"],
            "operation": "set_track_properties",
            "payload": {
                "sequence_id": sequence_id,
                "track_id": track["id"],
                "muted": True,
                "locked": True,
            },
        },
    )
    assert configured.status_code == 200, configured.text
    state = configured.json()
    track = next(t for t in state["sequences"][0]["tracks"] if t["id"] == track["id"])
    assert track["muted"] is True
    assert track["locked"] is True

    # Locked tracks reject destructive edits.
    locked_remove = session.post(
        f"{api_url}/projects/{project['id']}/operations",
        headers=headers,
        json={
            "expected_version": state["version"],
            "operation": "remove_track",
            "payload": {"sequence_id": sequence_id, "track_id": track["id"]},
        },
    )
    assert locked_remove.status_code == 409
    assert locked_remove.json()["error"]["code"] == "edit.track_locked"

    unlocked = session.post(
        f"{api_url}/projects/{project['id']}/operations",
        headers=headers,
        json={
            "expected_version": state["version"],
            "operation": "set_track_properties",
            "payload": {
                "sequence_id": sequence_id,
                "track_id": track["id"],
                "locked": False,
            },
        },
    )
    assert unlocked.status_code == 200
    state = unlocked.json()

    removed = session.post(
        f"{api_url}/projects/{project['id']}/operations",
        headers=headers,
        json={
            "expected_version": state["version"],
            "operation": "remove_track",
            "payload": {"sequence_id": sequence_id, "track_id": track["id"]},
        },
    )
    assert removed.status_code == 200
    assert all(
        t["id"] != track["id"] for t in removed.json()["sequences"][0]["tracks"]
    )
