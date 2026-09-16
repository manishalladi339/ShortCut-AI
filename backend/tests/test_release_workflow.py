"""Release regressions against a running API, real MongoDB and real FFmpeg.

Worker tests require MONGO_URL/DB_NAME to refer to the API's test database.
Never point this suite at a production database.
"""

import asyncio
import os
from pathlib import Path
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import pytest
import requests


def _project(api_url, headers):
    r = requests.post(
        f"{api_url}/projects",
        headers=headers,
        json={
            "title": "Release test",
            "content_type": "podcast",
            "creation_mode": "create_with_me",
        },
        timeout=10,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_local_file_links_are_scoped_expiring_and_immutable(api_url, fresh_user):
    headers = fresh_user["auth_headers"]
    r = requests.post(
        f"{api_url}/assets/presign-upload",
        headers=headers,
        json={
            "filename": "test.mp4",
            "kind": "video",
            "mime_type": "video/mp4",
            "size_bytes": 5,
        },
        timeout=10,
    )
    assert r.status_code == 201, r.text
    signed = r.json()
    bare = signed["upload_url"].split("?")[0]
    assert requests.put(bare, data=b"HELLO", timeout=10).status_code == 403
    assert requests.get(bare, timeout=10).status_code == 403
    assert (
        requests.put(signed["upload_url"], data=b"TOO LONG", timeout=10).status_code
        == 413
    )
    assert (
        requests.put(signed["upload_url"], data=b"HELLO", timeout=10).status_code == 200
    )
    assert (
        requests.put(signed["upload_url"], data=b"OTHER", timeout=10).status_code == 409
    )
    result = requests.post(
        f"{api_url}/assets/{signed['asset_id']}/confirm",
        headers=headers,
        json={},
        timeout=10,
    )
    assert result.status_code == 200, result.text
    url = result.json()["download_url"]
    assert requests.get(url, timeout=10).content == b"HELLO"
    partial = requests.get(url, headers={"Range": "bytes=1-3"}, timeout=10)
    assert partial.status_code == 206 and partial.content == b"ELL"
    assert (
        requests.get(url, headers={"Range": "bytes=10-20"}, timeout=10).status_code
        == 416
    )
    assert requests.put(url, data=b"OTHER", timeout=10).status_code == 403
    assert (
        requests.get(url.replace("signature=", "signature=bad"), timeout=10).status_code
        == 403
    )


def test_refresh_is_single_use_under_concurrency(api_url, fresh_user):
    token = fresh_user["refresh_token"]

    def refresh(_):
        return requests.post(
            f"{api_url}/auth/refresh", json={"refresh_token": token}, timeout=10
        ).status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sorted(pool.map(refresh, range(4))) == [200, 401, 401, 401]


def test_quota_cannot_be_bypassed_concurrently_or_by_duplicate(api_url, fresh_user):
    headers = fresh_user["auth_headers"]
    pid = _project(api_url, headers)

    def duplicate(_):
        return requests.post(
            f"{api_url}/projects/{pid}/duplicate", headers=headers, timeout=10
        ).status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert sorted(pool.map(duplicate, range(4))) == [201, 201, 402, 402]


def test_upload_edit_export_real_video(api_url, fresh_user, tmp_path):
    headers = fresh_user["auth_headers"]
    pid = _project(api_url, headers)
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=blue:s=160x90:d=2:r=30",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-shortest",
            str(source),
        ],
        check=True,
        timeout=30,
    )
    result = requests.post(
        f"{api_url}/assets/presign-upload",
        headers=headers,
        json={
            "filename": "source.mp4",
            "mime_type": "video/mp4",
            "kind": "video",
            "size_bytes": source.stat().st_size,
            "project_id": pid,
        },
        timeout=10,
    )
    assert result.status_code == 201, result.text
    signed = result.json()
    assert (
        requests.put(
            signed["upload_url"], data=source.read_bytes(), timeout=10
        ).status_code
        == 200
    )
    confirmed = requests.post(
        f"{api_url}/assets/{signed['asset_id']}/confirm",
        headers=headers,
        json={},
        timeout=10,
    )
    assert confirmed.status_code == 200, confirmed.text
    backend = Path(__file__).resolve().parents[1]
    # Drain only this test database's pending ingestion jobs.
    code = "import asyncio\nfrom workers.media_worker import process_one\nasync def main():\n for _ in range(30):\n  if not await process_one(): break\nasyncio.run(main())"
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=backend,
        check=True,
        timeout=90,
        capture_output=True,
    )
    asset = requests.get(
        f"{api_url}/assets/{signed['asset_id']}", headers=headers, timeout=10
    ).json()
    assert asset["processing_status"] == "ready", asset
    state = requests.get(
        f"{api_url}/projects/{pid}/state", headers=headers, timeout=10
    ).json()
    seq = state["sequences"][0]
    seq["width"] = 160
    seq["height"] = 90
    seq["tracks"][0]["clips"] = [
        {
            "id": "test-clip",
            "asset_id": asset["id"],
            "timeline_start": 0,
            "duration": 1500,
            "source_start": 250,
            "source_duration": 1500,
        }
    ]
    replaced = requests.put(
        f"{api_url}/projects/{pid}/state",
        headers=headers,
        json={
            "expected_version": 1,
            "active_sequence_id": seq["id"],
            "sequences": [seq],
        },
        timeout=10,
    )
    assert replaced.status_code == 200, replaced.text
    # Guard the source bounds before committing a new version.
    bad = requests.post(
        f"{api_url}/projects/{pid}/operations",
        headers=headers,
        json={
            "expected_version": 2,
            "operation": "trim_clip",
            "payload": {
                "sequence_id": seq["id"],
                "track_id": seq["tracks"][0]["id"],
                "clip_id": "test-clip",
                "source_start": 999999,
            },
        },
        timeout=10,
    )
    assert bad.status_code == 422, bad.text
    caption = requests.post(
        f"{api_url}/projects/{pid}/operations",
        headers=headers,
        json={
            "expected_version": 2,
            "operation": "add_caption",
            "payload": {
                "sequence_id": seq["id"],
                "text": "ShortCut export test",
                "start": 0,
                "duration": 1200,
            },
        },
        timeout=10,
    )
    assert caption.status_code == 200, caption.text
    exported = requests.post(
        f"{api_url}/projects/{pid}/exports",
        headers=headers,
        json={"preset": "source"},
        timeout=10,
    )
    assert exported.status_code == 202, exported.text
    e = exported.json()
    subprocess.run(
        [sys.executable, "-m", "workers.render_worker", "--once"],
        cwd=backend,
        check=True,
        timeout=90,
        capture_output=True,
    )
    finished = requests.get(
        f"{api_url}/projects/{pid}/exports/{e['id']}", headers=headers, timeout=10
    ).json()
    assert finished["status"] == "completed", requests.get(
        f"{api_url}/jobs/{e['job_id']}", headers=headers, timeout=10
    ).text
    video = requests.get(finished["download_url"], timeout=10)
    assert video.status_code == 200 and len(video.content) > 1000
    assert finished["project_state_version"] == 3
    assert abs(finished["duration_sec"] - 1.5) < 0.15
    assert finished["render_metadata"]["width"] == 160
    # Deleting a project invalidates access to its state and saved export records.
    assert (
        requests.delete(
            f"{api_url}/projects/{pid}", headers=headers, timeout=10
        ).status_code
        == 200
    )
    assert (
        requests.get(
            f"{api_url}/projects/{pid}/exports/{e['id']}", headers=headers, timeout=10
        ).status_code
        == 404
    )
    assert (
        requests.post(
            f"{api_url}/projects/{pid}/render-plan", headers=headers, timeout=10
        ).status_code
        == 404
    )
