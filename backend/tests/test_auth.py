"""Auth and account-lifecycle endpoint tests."""
import uuid

import requests


def test_signup_returns_user_and_tokens(api_url, session):
    email = f"test_{uuid.uuid4().hex[:10]}@shortcut.ai"
    r = session.post(
        f"{api_url}/auth/signup",
        json={"email": email, "password": "Demo12345!", "name": "Auth Sign", "accept_terms": True},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert "user" in body and "access_token" in body and "refresh_token" in body
    assert body["user"]["email"] == email
    assert body["user"]["subscription_tier"] == "free"


def test_signup_duplicate_email_409(api_url, session, fresh_user):
    r = session.post(
        f"{api_url}/auth/signup",
        json={"email": fresh_user["email"], "password": "Anything123!", "name": "x", "accept_terms": True},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "auth.email_taken"


def test_login_success(api_url, session, fresh_user):
    r = session.post(
        f"{api_url}/auth/login",
        json={"email": fresh_user["email"], "password": fresh_user["password"]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["email"] == fresh_user["email"]
    assert body["access_token"] and body["refresh_token"]


def test_login_wrong_password_401(api_url, session, fresh_user):
    r = session.post(
        f"{api_url}/auth/login",
        json={"email": fresh_user["email"], "password": "WrongPass1!"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "auth.invalid_credentials"


def test_login_unknown_email_401(api_url, session):
    r = session.post(
        f"{api_url}/auth/login",
        json={
            "email": f"nobody_{uuid.uuid4().hex[:6]}@shortcut.ai",
            "password": "Whatever1!",
        },
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "auth.invalid_credentials"


def test_me_with_token(api_url, fresh_user):
    r = requests.get(
        f"{api_url}/auth/me", headers=fresh_user["auth_headers"], timeout=10
    )
    assert r.status_code == 200
    assert r.json()["email"] == fresh_user["email"]


def test_me_missing_token_401(api_url):
    r = requests.get(f"{api_url}/auth/me", timeout=10)
    assert r.status_code == 401


def test_me_invalid_token_401(api_url):
    r = requests.get(
        f"{api_url}/auth/me",
        headers={"Authorization": "Bearer not-a-jwt"},
        timeout=10,
    )
    assert r.status_code == 401


def test_refresh_rotates_token(api_url, session, fresh_user):
    old = fresh_user["refresh_token"]
    r = session.post(f"{api_url}/auth/refresh", json={"refresh_token": old})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["refresh_token"] != old
    r2 = session.post(f"{api_url}/auth/refresh", json={"refresh_token": old})
    assert r2.status_code == 401


def test_forgot_password_always_ok(api_url, session, fresh_user):
    r = session.post(
        f"{api_url}/auth/forgot-password", json={"email": fresh_user["email"]}
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    r2 = session.post(
        f"{api_url}/auth/forgot-password",
        json={"email": f"nope_{uuid.uuid4().hex[:6]}@x.com"},
    )
    assert r2.status_code == 200
    assert r2.json() == {"ok": True}


def test_legacy_google_bridge_is_disabled(api_url, session):
    r = session.post(
        f"{api_url}/auth/google",
        json={"session_token": "random-not-valid-token"},
    )
    assert r.status_code == 410
    assert r.json()["error"]["code"] == "auth.google_disabled"


def test_delete_account_invalidates_access_and_releases_email(
    api_url, session, fresh_user
):
    headers = fresh_user["auth_headers"]
    deleted = session.delete(f"{api_url}/users/me", headers=headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"ok": True}

    me = session.get(f"{api_url}/auth/me", headers=headers)
    assert me.status_code == 401

    recreated = session.post(
        f"{api_url}/auth/signup",
        json={
            "email": fresh_user["email"],
            "password": "Demo12345!",
            "name": "Recreated User",
            "accept_terms": True,
        },
    )
    assert recreated.status_code == 201, recreated.text
