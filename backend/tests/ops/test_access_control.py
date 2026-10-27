"""Authentication and role checks across ALL Member 2 modules (docs/INTEGRATION_GUIDE.md section 6)."""
import pytest

from app.core.security import create_access_token, create_refresh_token
from tests.conftest import PASSWORD

PROTECTED_GETS = [
    "/api/v1/assignments",
    "/api/v1/exams",
    "/api/v1/grade-scales",
    "/api/v1/fee-invoices",
    "/api/v1/fee-heads",
    "/api/v1/period-definitions",
    "/api/v1/timetable/me",
    "/api/v1/events",
    "/api/v1/announcements",
    "/api/v1/notifications",
    "/api/v1/notifications/unread-count",
    "/api/v1/complaints",
    "/api/v1/lookups/sections",
]


@pytest.mark.parametrize("url", PROTECTED_GETS)
def test_no_token_is_401(client, url):
    r = client.get(url)
    assert r.status_code == 401, url
    assert r.json()["code"] == "not_authenticated"


def test_garbage_token_is_401(client, world):
    r = client.get("/api/v1/assignments", headers={"Authorization": "Bearer not-a-jwt"})
    assert r.status_code == 401


def test_expired_token_is_401_token_expired(client, world):
    token = create_access_token(world.admin.id, "admin", minutes=-5)
    r = client.get("/api/v1/exams", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert r.json()["code"] == "token_expired"


def test_refresh_token_cannot_be_used_as_access_token(client, world):
    token = create_refresh_token(world.admin.id, "admin")
    r = client.get("/api/v1/exams", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_deactivated_user_is_rejected_even_with_valid_token(client, db, world, h):
    headers = h(world.pu_a)
    assert client.get("/api/v1/notifications", headers=headers).status_code == 200
    world.pu_a.is_active = False
    db.add(world.pu_a)
    db.commit()
    assert client.get("/api/v1/notifications", headers=headers).status_code == 401


def test_token_with_wrong_role_claim_is_rejected(client, world):
    """A parent whose token claims role=admin must not become an admin."""
    token = create_access_token(world.pu_a.id, "admin")
    r = client.get("/api/v1/fee-heads", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


# (who, method, url) combinations that must be refused with 403. The body is empty on purpose:
# the role check runs before the body is looked at.
FORBIDDEN = [
    ("su_a1", "POST", "/api/v1/assignments"),
    ("pu_a", "POST", "/api/v1/assignments"),
    ("tu_a", "POST", "/api/v1/exams"),
    ("pu_a", "POST", "/api/v1/exams"),
    ("tu_a", "PUT", "/api/v1/grade-scales"),
    ("su_a1", "GET", "/api/v1/fee-invoices"),
    ("tu_a", "GET", "/api/v1/fee-invoices"),
    ("su_a1", "GET", "/api/v1/fee-heads"),
    ("pu_a", "POST", "/api/v1/fee-heads"),
    ("tu_a", "POST", "/api/v1/fee-invoices/generate"),
    ("pu_a", "GET", "/api/v1/fee-summary"),
    ("su_a1", "POST", "/api/v1/period-definitions"),
    ("tu_a", "POST", "/api/v1/timetable-slots"),
    ("su_a1", "POST", "/api/v1/events"),
    ("tu_a", "POST", "/api/v1/events"),
    ("pu_a", "POST", "/api/v1/announcements"),
    ("tu_a", "POST", "/api/v1/announcements"),
    ("tu_a", "GET", "/api/v1/complaints"),
    ("su_a1", "GET", "/api/v1/complaints"),
    ("su_a1", "POST", "/api/v1/complaints"),
    ("tu_a", "POST", "/api/v1/complaints"),
    ("su_a1", "GET", "/api/v1/lookups/students"),
    ("pu_a", "GET", "/api/v1/lookups/teachers"),
    ("tu_a", "GET", "/api/v1/lookups/teachers"),
    ("pu_a", "GET", "/api/v1/timetable/me"),
]


@pytest.mark.parametrize("who,method,url", FORBIDDEN)
def test_wrong_role_is_403(client, world, h, who, method, url):
    r = client.request(method, url, headers=h(getattr(world, who)), json={})
    assert r.status_code == 403, (who, method, url, r.text)
    assert r.json()["code"] == "forbidden"


# ---- the temporary login endpoint enforces the web/mobile rule from API_CONTRACT section 2 ----
def _login(client, login_id, platform, password=PASSWORD):
    headers = {"X-Client-Platform": platform} if platform else {}
    return client.post("/api/v1/auth/login", json={"login_id": login_id, "password": password}, headers=headers)


@pytest.mark.parametrize(
    "login_id,platform,expected",
    [
        ("admin", "web", 200),
        ("admin", "mobile", 403),
        ("t.ahmed", "web", 200),
        ("t.ahmed", "mobile", 200),
        ("s.a1", "mobile", 200),
        ("s.a1", "web", 403),
        ("p.a", "mobile", 200),
        ("p.a", "web", 403),
    ],
)
def test_platform_rule(client, world, login_id, platform, expected):
    assert _login(client, login_id, platform).status_code == expected


def test_wrong_password_is_401(client, world):
    r = _login(client, "admin", "web", password="not-the-password")
    assert r.status_code == 401


def test_login_returns_usable_tokens(client, world):
    body = _login(client, "p.a", "mobile").json()
    assert body["user"]["role"] == "parent"
    r = client.get("/api/v1/notifications", headers={"Authorization": "Bearer " + body["access_token"]})
    assert r.status_code == 200


def test_missing_platform_header_is_422(client, world):
    assert _login(client, "admin", None).status_code == 422
