#!/usr/bin/env python3
"""Real production smoke test for a deployed ShortCut AI environment.

This intentionally exercises the real S3/OpenAI/worker/render path. It is not run in
CI because it requires production credentials, a real video and billable providers.
"""
from __future__ import annotations

import argparse
import mimetypes
import os
import sys
import time
from pathlib import Path

import requests


class SmokeError(RuntimeError):
    pass


def check(response: requests.Response, expected: tuple[int, ...] = (200,)) -> dict:
    if response.status_code not in expected:
        raise SmokeError(
            f"{response.request.method} {response.url} -> "
            f"{response.status_code}: {response.text[:1200]}"
        )
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError as exc:
        raise SmokeError(f"Expected JSON from {response.url}") from exc


def wait_job(session: requests.Session, api: str, job_id: str, timeout: int, label: str) -> dict:
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = check(session.get(f"{api}/jobs/{job_id}", timeout=30))
        status = last["status"]
        progress = last.get("progress", 0)
        print(f"{label}: {status} {progress}%")
        if status == "succeeded":
            return last
        if status == "failed":
            raise SmokeError(
                f"{label} failed: {last.get('error_code')} {last.get('error_message')}"
            )
        time.sleep(2)
    raise SmokeError(f"{label} timed out after {timeout}s; last={last}")


def auth(session: requests.Session, api: str, email: str, password: str) -> dict:
    login = session.post(
        f"{api}/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    if login.status_code == 200:
        return login.json()
    if login.status_code != 401:
        return check(login)

    signup = session.post(
        f"{api}/auth/signup",
        json={
            "email": email,
            "password": password,
            "name": "Production Smoke",
            "accept_terms": True,
        },
        timeout=30,
    )
    return check(signup, (201,))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True, help="e.g. https://api.example.com")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--media", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--delete-account", action="store_true")
    args = parser.parse_args()

    if not args.media.is_file():
        raise SmokeError(f"Media file does not exist: {args.media}")

    base = args.base_url.rstrip("/")
    api = f"{base}/api/v1"
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    print("1/10 readiness")
    ready = check(session.get(f"{api}/ready", timeout=30))
    if not ready.get("ok"):
        raise SmokeError(f"Deployment is not ready: {ready}")

    print("2/10 authenticate")
    tokens = auth(session, api, args.email, args.password)
    session.headers["Authorization"] = f"Bearer {tokens['access_token']}"
    check(session.get(f"{api}/auth/me", timeout=30))

    print("3/10 create project")
    project = check(
        session.post(
            f"{api}/projects",
            json={
                "title": f"PRODUCTION_SMOKE_{int(time.time())}",
                "description": "Automated deployed real-video smoke test",
                "content_type": "educational",
                "creation_mode": "create_for_me",
                "target_platforms": ["ig_reels"],
                "prompt": "Create a concise, coherent vertical short from the strongest moments.",
            },
            timeout=30,
        ),
        (201,),
    )
    project_id = project["id"]

    print("4/10 upload real media")
    mime = mimetypes.guess_type(args.media.name)[0] or "video/mp4"
    if not mime.startswith("video/"):
        raise SmokeError("Smoke test currently expects a video file")
    presign = check(
        session.post(
            f"{api}/assets/presign-upload",
            json={
                "filename": args.media.name,
                "mime_type": mime,
                "kind": "video",
                "size_bytes": args.media.stat().st_size,
                "project_id": project_id,
                "tags": ["production-smoke"],
            },
            timeout=30,
        ),
        (201,),
    )
    with args.media.open("rb") as handle:
        upload_headers = {
            k: v for k, v in presign.get("upload_headers", {}).items() if k.lower() != "content-length"
        }
        uploaded = requests.put(
            presign["upload_url"],
            data=handle,
            headers=upload_headers,
            timeout=max(120, args.timeout),
        )
    if uploaded.status_code not in (200, 201, 204):
        raise SmokeError(f"Binary upload failed: {uploaded.status_code} {uploaded.text[:500]}")

    asset = check(
        session.post(
            f"{api}/assets/{presign['asset_id']}/confirm",
            json={},
            timeout=30,
        )
    )
    wait_job(session, api, asset["processing_job_id"], args.timeout, "media processing")

    print("5/10 media intelligence")
    analysis = check(
        session.post(f"{api}/assets/{asset['id']}/analyze", timeout=30),
        (202,),
    )
    wait_job(session, api, analysis["job_id"], args.timeout, "media intelligence")

    print("6/10 build and apply AI Director plan")
    state = check(session.get(f"{api}/projects/{project_id}/state", timeout=30))
    plan = check(
        session.post(
            f"{api}/projects/{project_id}/ai-plans",
            json={
                "objective": "Create a strong coherent vertical short from this source.",
                "director_mode": "standard",
                "target_duration_sec": 45,
                "max_clips": 8,
                "include_captions": True,
                "remove_dead_air": True,
                "rhythm_snap_broll": True,
                "broll_fade": True,
                "smart_reframe": True,
                "music_ducking": True,
            },
            timeout=max(120, args.timeout),
        ),
        (201,),
    )
    state = check(
        session.post(
            f"{api}/projects/{project_id}/ai-plans/{plan['id']}/apply",
            json={
                "expected_version": plan["project_state_version"],
                "replace_existing_video_clips": False,
            },
            timeout=60,
        )
    )

    print("7/10 Create With Me adjustment")
    proposal = check(
        session.post(
            f"{api}/projects/{project_id}/constrained-edits",
            json={"instruction": "Make the captions pop"},
            timeout=60,
        )
    )
    if proposal.get("operations"):
        state = check(
            session.post(
                f"{api}/projects/{project_id}/constrained-edits/{proposal['id']}/apply",
                json={"expected_version": proposal["project_state_version"]},
                timeout=60,
            )
        )
    else:
        raise SmokeError("Create With Me proposal contained no operations")

    print("8/10 render vertical export")
    export = check(
        session.post(
            f"{api}/projects/{project_id}/exports",
            json={
                "sequence_id": state["active_sequence_id"],
                "preset": "vertical_1080p",
            },
            timeout=60,
        ),
        (202,),
    )
    wait_job(session, api, export["job_id"], args.timeout, "render")
    export = check(
        session.get(
            f"{api}/projects/{project_id}/exports/{export['id']}",
            timeout=30,
        )
    )
    if export.get("status") != "completed" or not export.get("download_url"):
        raise SmokeError(f"Export incomplete: {export}")

    print("9/10 verify final artifact and QA")
    result = requests.get(export["download_url"], stream=True, timeout=120)
    if result.status_code != 200:
        raise SmokeError(f"Export download failed: {result.status_code}")
    first_chunk = next(result.iter_content(chunk_size=32), b"")
    result.close()
    if not first_chunk:
        raise SmokeError("Export download returned no bytes")
    if export.get("qa_status") not in {"passed", "warnings"}:
        raise SmokeError(f"Export QA did not pass: {export.get('qa_status')}")

    print("10/10 cleanup")
    if args.delete_account:
        deleted = check(
            session.delete(
                f"{api}/users/me",
                json={"confirmation": "DELETE"},
                timeout=60,
            )
        )
        if not deleted.get("ok"):
            raise SmokeError(f"Account deletion failed: {deleted}")
        print("Test account deleted.")
    else:
        check(session.delete(f"{api}/projects/{project_id}", timeout=30))
        print("Project removed; test account retained.")

    print("PUBLIC-BETA PRODUCTION SMOKE: PASS")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeError as exc:
        print(f"PUBLIC-BETA PRODUCTION SMOKE: FAIL\n{exc}", file=sys.stderr)
        raise SystemExit(1)
