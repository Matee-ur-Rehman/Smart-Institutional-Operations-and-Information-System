"""Authentication: login rules, lock-out, refresh rotation/replay, logout, password change, profile."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.core.security import create_access_token
from app.modules.foundation.models import User
from tests.conftest import PASSWORD


def login(api, login_id, password=PASSWORD, platform="web"):
    return api.post("/auth/login", None, json={"login_id": login_id, "password": password}, headers={"X-Client-Platform": platform})


def test_login_success_and_platform_rules(api, world):
    r = login(api, "admin")
    assert r.status_code == 200
    d = r.json()
    assert d["token_type"] == "bearer" and d["user"]["role"] == "admin" and "password_hash" not in str(d)
    assert login(api, "ADMIN").status_code == 200                       # case-insensitive login id
    assert login(api, "t.a", platform="web").status_code == 200          # teacher: both platforms
    assert login(api, "t.a", platform="mobile").status_code == 200
    assert login(api, "admin", platform="mobile").status_code == 403
    assert login(api, "s.a1", platform="web").status_code == 403
    assert login(api, "p.1", platform="web").status_code == 403
    assert login(api, "s.a1", platform="mobile").status_code == 200
    assert api.post("/auth/login", None, json={"login_id": "admin", "password": PASSWORD}).status_code == 422   # header missing


def test_bad_credentials_are_indistinguishable(api, world):
    a = login(api, "admin", "WrongPass1")
    b = login(api, "nobody", "WrongPass1")
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"] == b.json()["detail"] and a.json()["code"] == "invalid_credentials"


def test_inactive_user_cannot_login_or_use_token(api, world, db):
    w = world
    token_headers = {"Authorization": f"Bearer {create_access_token(w.ua.id, w.ua.role)}"}
    assert api.get("/auth/me", None, headers=token_headers).status_code == 200
    db.execute(update(User).where(User.id == w.ua.id).values(is_active=False))
    db.commit()
    assert login(api, "t.a").status_code == 401
    assert api.get("/auth/me", None, headers=token_headers).status_code == 401


def test_lockout_after_repeated_failures(api, world, db):
    w = world
    for _ in range(5):
        assert login(api, "t.b", "WrongPass1").status_code == 401
    r = login(api, "t.b", PASSWORD)                                      # right password, but locked
    assert r.status_code == 429 and r.json()["code"] == "too_many_attempts"
    # admin unlock
    assert api.post(f"/users/{w.ub.id}/unlock", w.admin).status_code == 204
    assert login(api, "t.b", PASSWORD).status_code == 200
    # a successful login resets the counter
    for _ in range(3):
        login(api, "t.b", "WrongPass1")
    assert login(api, "t.b", PASSWORD).status_code == 200
    for _ in range(4):
        login(api, "t.b", "WrongPass1")
    assert login(api, "t.b", PASSWORD).status_code == 200


def test_lock_expires(api, world, db):
    w = world
    db.execute(update(User).where(User.id == w.ub.id).values(locked_until=datetime.now(timezone.utc) - timedelta(minutes=1)))
    db.commit()
    assert login(api, "t.b").status_code == 200


def test_refresh_rotation_and_replay_detection(api, world):
    first = login(api, "t.a").json()
    r = api.post("/auth/refresh", None, json={"refresh_token": first["refresh_token"]})
    assert r.status_code == 200
    second = r.json()
    assert second["refresh_token"] != first["refresh_token"]
    # replaying the first (already used) token: rejected AND every session of that user is revoked
    bad = api.post("/auth/refresh", None, json={"refresh_token": first["refresh_token"]})
    assert bad.status_code == 401 and bad.json()["code"] == "token_reused"
    assert api.post("/auth/refresh", None, json={"refresh_token": second["refresh_token"]}).status_code == 401
    assert api.post("/auth/refresh", None, json={"refresh_token": "garbage"}).status_code == 401
    # an access token is not a refresh token
    assert api.post("/auth/refresh", None, json={"refresh_token": first["access_token"]}).status_code == 401


def test_logout_revokes_refresh_tokens(api, world):
    s1, s2 = login(api, "t.a").json(), login(api, "t.a", platform="mobile").json()
    h1 = {"Authorization": f"Bearer {s1['access_token']}"}
    assert api.post("/auth/logout", None, headers=h1, json={"refresh_token": s1["refresh_token"]}).status_code == 204
    assert api.post("/auth/refresh", None, json={"refresh_token": s1["refresh_token"]}).status_code == 401
    assert api.post("/auth/refresh", None, json={"refresh_token": s2["refresh_token"]}).status_code == 200   # other session survives
    s3 = login(api, "t.a").json()
    h3 = {"Authorization": f"Bearer {s3['access_token']}"}
    assert api.post("/auth/logout", None, headers=h3).status_code == 204                                   # no body: all sessions
    assert api.post("/auth/refresh", None, json={"refresh_token": s3["refresh_token"]}).status_code == 401
    assert api.post("/auth/logout", None).status_code == 401


def test_change_password(api, world):
    w = world
    s = login(api, "t.a").json()
    bearer = {"Authorization": f"Bearer {s['access_token']}"}
    url = "/auth/change-password"
    assert api.post(url, None, headers=bearer, json={"current_password": "Nope12345", "new_password": "NewPass123"}).status_code == 400
    assert api.post(url, None, headers=bearer, json={"current_password": PASSWORD, "new_password": "short1"}).status_code == 422
    assert api.post(url, None, headers=bearer, json={"current_password": PASSWORD, "new_password": "onlyletters"}).status_code == 422
    assert api.post(url, None, headers=bearer, json={"current_password": PASSWORD, "new_password": PASSWORD}).status_code == 400
    assert api.post(url, None, headers=bearer, json={"current_password": PASSWORD, "new_password": "NewPass123"}).status_code == 204
    assert login(api, "t.a", PASSWORD).status_code == 401
    assert login(api, "t.a", "NewPass123").status_code == 200
    assert api.post("/auth/refresh", None, json={"refresh_token": s["refresh_token"]}).status_code == 401   # old sessions ended


def test_profile_update(api, world):
    w = world
    r = api.patch("/auth/me", w.ua, json={"phone": "0300-1112223", "email": "teacher.a@example.com"})
    assert r.status_code == 200 and r.json()["phone"] == "0300-1112223"
    assert api.patch("/auth/me", w.ua, json={"phone": "abc"}).status_code == 422
    assert api.patch("/auth/me", w.ua, json={"email": "not-an-email"}).status_code == 422
    assert api.patch("/auth/me", w.ub, json={"email": "teacher.a@example.com"}).status_code == 409
    assert api.patch("/auth/me", None, json={}).status_code == 401
    # role / is_active cannot be changed through this endpoint
    api.patch("/auth/me", w.ua, json={"role": "admin", "is_active": False})
    assert api.get("/auth/me", w.ua).json()["role"] == "teacher"
