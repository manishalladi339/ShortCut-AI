"""Asset upload and processing-queue integration tests."""
import requests


def test_presign_upload_creates_pending_asset(api_url, session, fresh_user):
    headers = fresh_user["auth_headers"]
    payload = {
        "filename": "TEST_clip.mp4",
        "mime_type": "video/mp4",
        "kind": "video",
        "size_bytes": 1234,
        "tags": ["test"],
    }
    response = session.post(f"{api_url}/assets/presign-upload", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    body = response.json()
    for key in ("asset_id", "upload_url", "upload_headers", "storage_key", "expires_at"):
        assert key in body

    response = session.get(f"{api_url}/assets", headers=headers)
    assert response.status_code == 200
    asset = next(
        item for item in response.json()["items"] if item["id"] == body["asset_id"]
    )
    assert asset["upload_status"] == "pending"
    assert asset["processing_status"] == "pending"


def test_full_upload_confirmation_enqueues_processing_job(
    api_url, base_url, session, fresh_user
):
    headers = fresh_user["auth_headers"]
    response = session.post(
        f"{api_url}/assets/presign-upload",
        json={
            "filename": "TEST_full.mp4",
            "mime_type": "video/mp4",
            "kind": "video",
            "size_bytes": 5,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    presigned = response.json()
    asset_id = presigned["asset_id"]
    upload_url = presigned["upload_url"]
    if upload_url.startswith("/"):
        upload_url = base_url + upload_url

    binary = b"HELLO"
    put = requests.put(
        upload_url,
        data=binary,
        headers=presigned["upload_headers"],
        timeout=20,
    )
    assert put.status_code == 200, put.text

    response = session.post(
        f"{api_url}/assets/{asset_id}/confirm",
        json={},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    confirmed = response.json()
    assert confirmed["upload_status"] == "uploaded"
    assert confirmed["processing_status"] == "queued"
    assert confirmed["processing_job_id"]
    assert confirmed["size_bytes"] == len(binary)
    assert confirmed["download_url"]

    job_response = session.get(
        f"{api_url}/jobs/{confirmed['processing_job_id']}", headers=headers
    )
    assert job_response.status_code == 200
    assert job_response.json()["type"] == "media_probe"
    assert job_response.json()["status"] == "queued"

    # Reconfirm is idempotent and returns the same processing job.
    second = session.post(
        f"{api_url}/assets/{asset_id}/confirm", json={}, headers=headers
    )
    assert second.status_code == 200
    assert second.json()["processing_job_id"] == confirmed["processing_job_id"]

    response = session.get(f"{api_url}/assets?kind=video", headers=headers)
    assert response.status_code == 200
    assert any(item["id"] == asset_id for item in response.json()["items"])

    response = session.delete(f"{api_url}/assets/{asset_id}", headers=headers)
    assert response.status_code == 200
    response = session.get(f"{api_url}/assets/{asset_id}", headers=headers)
    assert response.status_code == 404


def test_confirm_without_upload_400(api_url, session, fresh_user):
    headers = fresh_user["auth_headers"]
    response = session.post(
        f"{api_url}/assets/presign-upload",
        json={
            "filename": "TEST_noput.mp4",
            "mime_type": "video/mp4",
            "kind": "video",
            "size_bytes": 10,
        },
        headers=headers,
    )
    asset_id = response.json()["asset_id"]

    response = session.post(
        f"{api_url}/assets/{asset_id}/confirm", json={}, headers=headers
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "asset.binary_missing"


def test_assets_require_auth(api_url, session):
    response = session.get(f"{api_url}/assets")
    assert response.status_code == 401
