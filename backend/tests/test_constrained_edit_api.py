"""API integration tests for constrained Create-With-Me editing."""


def _project_payload():
    return {
        "title": "TEST_Constrained_Edit",
        "content_type": "podcast",
        "creation_mode": "create_with_me",
        "target_platforms": ["ig_reels"],
    }


def _create_project_with_caption(api_url, session, headers):
    project = session.post(
        f"{api_url}/projects",
        json=_project_payload(),
        headers=headers,
    ).json()
    state = session.get(
        f"{api_url}/projects/{project['id']}/state",
        headers=headers,
    ).json()
    added = session.post(
        f"{api_url}/projects/{project['id']}/operations",
        headers=headers,
        json={
            "expected_version": state["version"],
            "operation": "add_caption",
            "payload": {
                "sequence_id": state["active_sequence_id"],
                "start": 0,
                "duration": 5000,
                "text": "Grounded caption",
                "style": {"source": "transcript"},
            },
        },
    )
    assert added.status_code == 200, added.text
    return project, added.json()


def test_constrained_caption_edit_previews_then_applies_atomically(
    api_url, session, fresh_user
):
    headers = fresh_user["auth_headers"]
    project, state = _create_project_with_caption(api_url, session, headers)

    preview = session.post(
        f"{api_url}/projects/{project['id']}/constrained-edits",
        headers=headers,
        json={"instruction": "Remove captions from the intro"},
    )
    assert preview.status_code == 200, preview.text
    proposal = preview.json()
    assert proposal["project_state_version"] == state["version"]
    assert proposal["interpreted_intents"] == ["remove_captions"]
    assert len(proposal["operations"]) == 1
    assert proposal["operations"][0]["operation"] == "remove_caption"

    applied = session.post(
        f"{api_url}/projects/{project['id']}/constrained-edits/{proposal['id']}/apply",
        headers=headers,
        json={
            "expected_version": state["version"],
            "operation_ids": [proposal["operations"][0]["id"]],
        },
    )
    assert applied.status_code == 200, applied.text
    next_state = applied.json()
    assert next_state["version"] == state["version"] + 1
    assert next_state["sequences"][0]["captions"] == []

    listed = session.get(
        f"{api_url}/projects/{project['id']}/constrained-edits",
        headers=headers,
    )
    assert listed.status_code == 200
    assert listed.json()[0]["status"] == "applied"


def test_constrained_edit_rejects_stale_timeline(api_url, session, fresh_user):
    headers = fresh_user["auth_headers"]
    project, state = _create_project_with_caption(api_url, session, headers)

    preview = session.post(
        f"{api_url}/projects/{project['id']}/constrained-edits",
        headers=headers,
        json={"instruction": "Make captions smaller"},
    )
    assert preview.status_code == 200, preview.text
    proposal = preview.json()

    renamed = session.post(
        f"{api_url}/projects/{project['id']}/operations",
        headers=headers,
        json={
            "expected_version": state["version"],
            "operation": "rename_sequence",
            "payload": {
                "sequence_id": state["active_sequence_id"],
                "name": "Changed after AI preview",
            },
        },
    )
    assert renamed.status_code == 200

    stale = session.post(
        f"{api_url}/projects/{project['id']}/constrained-edits/{proposal['id']}/apply",
        headers=headers,
        json={"expected_version": proposal["project_state_version"]},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "project_state.version_conflict"


def test_unsupported_primary_cut_instruction_leaves_state_untouched(
    api_url, session, fresh_user
):
    headers = fresh_user["auth_headers"]
    project, state = _create_project_with_caption(api_url, session, headers)

    response = session.post(
        f"{api_url}/projects/{project['id']}/constrained-edits",
        headers=headers,
        json={"instruction": "Make the intro faster"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "constrained_edit.unsupported_or_empty"

    after = session.get(
        f"{api_url}/projects/{project['id']}/state",
        headers=headers,
    )
    assert after.status_code == 200
    assert after.json()["version"] == state["version"]
    assert after.json()["sequences"][0]["captions"][0]["text"] == "Grounded caption"
