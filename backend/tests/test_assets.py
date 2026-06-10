"""Asset upload flow tests via stub S3."""
import requests


def test_presign_upload_creates_pending_asset(api_url, session, fresh_user):
    h = fresh_user["auth_headers"]
    payload = {
        "filename": "TEST_clip.mp4",
        "mime_type": "video/mp4",
        "kind": "video",
        "size_bytes": 1234,
        "tags": ["test"],
    }
    r = session.post(f"{api_url}/assets/presign-upload", json=payload, headers=h)
    assert r.status_code == 201, r.text
    body = r.json()
    for k in ("asset_id", "upload_url", "upload_headers", "s3_key", "expires_at"):
        assert k in body
    # Asset listed and pending
    r = session.get(f"{api_url}/assets", headers=h)
    assert r.status_code == 200
    items = r.json()["items"]
    asset = next((a for a in items if a["id"] == body["asset_id"]), None)
    assert asset is not None
    assert asset["upload_status"] == "pending"


def test_full_upload_lifecycle(api_url, base_url, session, fresh_user):
    h = fresh_user["auth_headers"]
    # Presign
    r = session.post(
        f"{api_url}/assets/presign-upload",
        json={
            "filename": "TEST_full.mp4",
            "mime_type": "video/mp4",
            "kind": "video",
            "size_bytes": 5,
        },
        headers=h,
    )
    assert r.status_code == 201, r.text
    pre = r.json()
    asset_id = pre["asset_id"]
    upload_url = pre["upload_url"]
    # Ensure absolute URL
    if upload_url.startswith("/"):
        upload_url = base_url + upload_url

    # PUT bytes to stub storage
    binary = b"HELLO"
    put = requests.put(upload_url, data=binary, headers=pre["upload_headers"], timeout=20)
    assert put.status_code == 200, f"{put.status_code} {put.text}"

    # Confirm
    r = session.post(f"{api_url}/assets/{asset_id}/confirm", json={"width": 1080, "height": 1920}, headers=h)
    assert r.status_code == 200, r.text
    confirmed = r.json()
    assert confirmed["upload_status"] == "uploaded"
    assert confirmed["size_bytes"] == len(binary)
    assert confirmed["s3_url"]  # presigned download

    # Filter list by kind
    r = session.get(f"{api_url}/assets?kind=video", headers=h)
    assert r.status_code == 200
    assert any(a["id"] == asset_id for a in r.json()["items"])

    # Filter by q (filename regex)
    r = session.get(f"{api_url}/assets?q=TEST_full", headers=h)
    assert r.status_code == 200
    assert any(a["id"] == asset_id for a in r.json()["items"])

    # Delete asset
    r = session.delete(f"{api_url}/assets/{asset_id}", headers=h)
    assert r.status_code == 200

    # Confirm 404 after delete
    r = session.get(f"{api_url}/assets/{asset_id}", headers=h)
    assert r.status_code == 404


def test_confirm_without_upload_400(api_url, session, fresh_user):
    h = fresh_user["auth_headers"]
    r = session.post(
        f"{api_url}/assets/presign-upload",
        json={"filename": "TEST_noput.mp4", "mime_type": "video/mp4", "kind": "video", "size_bytes": 10},
        headers=h,
    )
    asset_id = r.json()["asset_id"]
    # Skip PUT and confirm directly
    r = session.post(f"{api_url}/assets/{asset_id}/confirm", json={}, headers=h)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "asset.binary_missing"


def test_assets_require_auth(api_url, session):
    r = session.get(f"{api_url}/assets")
    assert r.status_code == 401
