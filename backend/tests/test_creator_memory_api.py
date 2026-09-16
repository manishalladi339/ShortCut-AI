"""API smoke tests for Creator Memory."""
def test_creator_memory_initializes_empty(api_url, session, fresh_user):
    headers = fresh_user["auth_headers"]

    response = session.get(
        f"{api_url}/users/me/creator-memory",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    memory = response.json()
    assert memory["evidence_count"] == 0
    assert memory["preferences"]["broll_density_multiplier"] == 1.0
    assert memory["preferences"]["music_volume_multiplier"] == 1.0
    assert "will learn" in memory["summary"]

    rebuilt = session.post(
        f"{api_url}/users/me/creator-memory/refresh",
        headers=headers,
    )
    assert rebuilt.status_code == 200, rebuilt.text
    assert rebuilt.json()["id"] == memory["id"]


def test_creator_memory_is_private(api_url, session, fresh_user):
    import uuid

    first_headers = fresh_user["auth_headers"]
    first = session.get(
        f"{api_url}/users/me/creator-memory",
        headers=first_headers,
    ).json()

    signup = session.post(
        f"{api_url}/auth/signup",
        json={
            "email": f"memory_{uuid.uuid4().hex[:8]}@shortcut.ai",
            "password": "Demo12345!",
            "name": "Memory User",
        },
    )
    assert signup.status_code in {200, 201}, signup.text
    second_headers = {
        "Authorization": f"Bearer {signup.json()['access_token']}"
    }
    second = session.get(
        f"{api_url}/users/me/creator-memory",
        headers=second_headers,
    )
    assert second.status_code == 200
    assert second.json()["id"] != first["id"]
