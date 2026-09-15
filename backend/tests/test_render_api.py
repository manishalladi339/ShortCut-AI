"""Render/export API contract tests."""


def _project_payload():
    return {
        "title": "TEST_Render",
        "content_type": "podcast",
        "creation_mode": "create_with_me",
        "target_platforms": ["ig_reels"],
    }


def test_empty_sequence_cannot_be_exported(api_url, session, fresh_user):
    headers = fresh_user["auth_headers"]
    project = session.post(
        f"{api_url}/projects", json=_project_payload(), headers=headers
    ).json()

    # Initialize canonical state first.
    state = session.get(
        f"{api_url}/projects/{project['id']}/state", headers=headers
    )
    assert state.status_code == 200

    plan = session.post(
        f"{api_url}/projects/{project['id']}/render-plan", headers=headers
    )
    assert plan.status_code == 200
    assert plan.json()["clips"] == []

    export = session.post(
        f"{api_url}/projects/{project['id']}/exports",
        headers=headers,
        json={"preset": "vertical_1080p"},
    )
    assert export.status_code == 422
    assert export.json()["error"]["code"] == "render.empty_sequence"
