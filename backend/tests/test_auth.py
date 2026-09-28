"""Auth endpoint tests."""
import uuid

import requests


def test_signup_returns_user_and_tokens(api_url, session):
    email = f"test_{uuid.uuid4().hex[:10]}@shortcut.ai"
    r = session.post(
        f"{api_url}/auth/signup",
        json={
            "email": email,
            "password": "Demo12345!",
            "name": "Auth Sign",
            "accept_terms": True,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert "user" in body and "access_token" in body and "refresh_token" in body
    assert body["user"]["email"] == email
    assert body["user"]["subscription_tier"] == "free"



def test_signup_requires_terms_acceptance(api_url, session):
    email = f"terms_{uuid.uuid4().hex[:10]}@shortcut.ai"
    r = session.post(
        f"{api_url}/auth/signup",
        json={
            "email": email,
            "password": "Demo12345!",
            "name": "Terms Test",
            "accept_terms": False,
        },
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "auth.terms_required"

def test_signup_duplicate_email_409(api_url, session, fresh_user):
    r = session.post(
        f"{api_url}/auth/signup",
        json={
            "email": fresh_user["email"],
            "password": "Anything123!",
            "name": "x",
            "accept_terms": True,
        },
    )
    assert r.status_code == 409
    body = r.json()
    assert body["error"]["code"] == "auth.email_taken"


def test_login_success(api_url, session, fresh_user):
    r = session.post(f"{api_url}/auth/login", json={"email": fresh_user["email"], "password": fresh_user["password"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["email"] == fresh_user["email"]
    assert body["access_token"] and body["refresh_token"]


def test_login_wrong_password_401(api_url, session, fresh_user):
    r = session.post(f"{api_url}/auth/login", json={"email": fresh_user["email"], "password": "WrongPass1!"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "auth.invalid_credentials"


def test_login_unknown_email_401(api_url, session):
    r = session.post(
        f"{api_url}/auth/login",
        json={"email": f"nobody_{uuid.uuid4().hex[:6]}@shortcut.ai", "password": "Whatever1!"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "auth.invalid_credentials"


def test_me_with_token(api_url, fresh_user):
    r = requests.get(f"{api_url}/auth/me", headers=fresh_user["auth_headers"], timeout=10)
    assert r.status_code == 200
    assert r.json()["email"] == fresh_user["email"]


def test_me_missing_token_401(api_url):
    r = requests.get(f"{api_url}/auth/me", timeout=10)
    assert r.status_code == 401


def test_me_invalid_token_401(api_url):
    r = requests.get(f"{api_url}/auth/me", headers={"Authorization": "Bearer not-a-jwt"}, timeout=10)
    assert r.status_code == 401


def test_refresh_rotates_token(api_url, session, fresh_user):
    old = fresh_user["refresh_token"]
    r = session.post(f"{api_url}/auth/refresh", json={"refresh_token": old})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["refresh_token"] != old
    # Using old refresh again should now fail (revoked)
    r2 = session.post(f"{api_url}/auth/refresh", json={"refresh_token": old})
    assert r2.status_code == 401


def test_forgot_password_always_ok(api_url, session, fresh_user):
    r = session.post(f"{api_url}/auth/forgot-password", json={"email": fresh_user["email"]})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    # Unknown email also returns ok (no enumeration)
    r2 = session.post(f"{api_url}/auth/forgot-password", json={"email": f"nope_{uuid.uuid4().hex[:6]}@x.com"})
    assert r2.status_code == 200
    assert r2.json() == {"ok": True}


def test_google_is_disabled_without_first_party_configuration(api_url, session):
    r = session.post(f"{api_url}/auth/google", json={"id_token": "not-a-real-google-id-token"})
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "auth.google_disabled"


def test_authenticated_user_can_delete_account(api_url, session, fresh_user):
    r = session.delete(
        f"{api_url}/users/me",
        headers=fresh_user["auth_headers"],
        json={"confirmation": "DELETE"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True

    me = session.get(f"{api_url}/auth/me", headers=fresh_user["auth_headers"])
    assert me.status_code == 401
