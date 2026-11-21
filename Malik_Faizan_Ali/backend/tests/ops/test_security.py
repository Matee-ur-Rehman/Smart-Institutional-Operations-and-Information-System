"""Every protected endpoint: 401 without/with bad token, 403 for roles the route does not allow.
Allowed roles are read from the real route dependencies (require_roles closures), so new routes are covered automatically."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.routing import APIRoute
from jose import jwt

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token
from app.main import API_PREFIX
from app.modules.announcements.router import router as r_ann
from app.modules.calendar.router import router as r_cal
from app.modules.complaints.router import router as r_cmp
from app.modules.exams.router import router as r_exm
from app.modules.fees.router import router as r_fee
from app.modules.foundation.auth_router import router as r_auth
from app.modules.homework.router import router as r_hw
from app.modules.lookups.router import router as r_lk
from app.modules.notifications.router import router as r_not
from app.modules.timetable.router import router as r_tt

# FastAPI >= 0.16x mounts routers lazily (app.routes holds opaque wrappers), so walk the module routers directly.
ROUTERS = (r_ann, r_cal, r_cmp, r_exm, r_fee, r_auth, r_hw, r_lk, r_not, r_tt)

PUBLIC = {("POST", f"{API_PREFIX}/auth/login"), ("POST", f"{API_PREFIX}/auth/refresh"), ("GET", f"{API_PREFIX}/health")}
ROLES = ("admin", "teacher", "student", "parent")
OPS_PREFIXES = ("assignments", "exams", "results", "fee-invoices", "timetable", "events", "announcements",
                "notifications", "devices", "complaints")


def _allowed_roles(dependant) -> set[str] | None:
    """None = any authenticated user; otherwise the roles of the require_roles() dependency."""
    found = None
    for d in dependant.dependencies:
        call = d.call
        if getattr(call, "__qualname__", "").startswith("require_roles.") and call.__closure__:
            for cell in call.__closure__:
                v = cell.cell_contents
                if isinstance(v, tuple) and all(isinstance(x, str) for x in v):
                    found = set(v) if found is None else found & set(v)
        sub = _allowed_roles(d)
        if sub is not None:
            found = sub if found is None else found & sub
    return found


def _routes():
    out = []
    for router in ROUTERS:
        for r in router.routes:
            if isinstance(r, APIRoute):
                full = API_PREFIX + r.path
                for m in r.methods - {"HEAD", "OPTIONS"}:
                    if (m, full) not in PUBLIC:
                        out.append((m, full, _allowed_roles(r.dependant)))
    return sorted(out, key=lambda x: (x[1], x[0]))


ROUTES = _routes()


def _fill(path: str) -> str:
    import re
    return re.sub(r"\{[^}]+\}", lambda m: str(uuid.uuid4()), path)


def test_routes_discovered_for_all_seven_modules():
    paths = {p for _, p, _ in ROUTES}
    for prefix in OPS_PREFIXES:
        assert any(f"{API_PREFIX}/{prefix}" in p for p in paths), f"no routes found for {prefix}"
    assert len(ROUTES) > 60


def _call(client, method, path, headers=None):
    return client.request(method, _fill(path), headers=headers or {}, json={} if method in ("POST", "PUT", "PATCH") else None)


@pytest.mark.parametrize("method,path,roles", ROUTES, ids=[f"{m} {p}" for m, p, _ in ROUTES])
def test_no_token_is_401(client, method, path, roles):
    r = _call(client, method, path)
    assert r.status_code == 401, r.text


@pytest.mark.parametrize("method,path,roles", ROUTES, ids=[f"{m} {p}" for m, p, _ in ROUTES])
def test_wrong_role_is_403(client, world, method, path, roles):
    from tests.conftest import bearer
    users = {"admin": world.admin, "teacher": world.ua, "student": world.user_a1, "parent": world.up1}
    if roles is None:
        pytest.skip("route open to every authenticated role")
    for role in ROLES:
        r = _call(client, method, path, bearer(users[role]))
        if role in roles:
            assert r.status_code not in (401, 403), f"{role} should be allowed: {r.status_code} {r.text}"
        else:
            assert r.status_code == 403, f"{role} should be forbidden on {method} {path}: {r.status_code}"


def test_garbage_and_wrong_scheme_tokens(api, world):
    for h in ({"Authorization": "Bearer not.a.jwt"}, {"Authorization": "Bearer "}, {"Authorization": "Basic abc"},
              {"Authorization": "garbage"}):
        assert api.get("/notifications", None, headers=h).status_code == 401


def test_expired_token(api, world):
    exp = jwt.encode({"sub": str(world.admin.id), "role": "admin", "type": "access",
                      "exp": int((datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp())},
                     settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    r = api.get("/events", None, headers={"Authorization": f"Bearer {exp}"})
    assert r.status_code == 401
    assert "expired" in r.text.lower()


def test_token_signed_with_wrong_key(api, world):
    t = jwt.encode({"sub": str(world.admin.id), "role": "admin", "type": "access",
                    "exp": int((datetime.now(timezone.utc) + timedelta(minutes=5)).timestamp())}, "another-secret", algorithm="HS256")
    assert api.get("/events", None, headers={"Authorization": f"Bearer {t}"}).status_code == 401


def test_refresh_token_not_accepted_as_access(api, world):
    t = create_refresh_token(world.admin.id, "admin")
    assert api.get("/events", None, headers={"Authorization": f"Bearer {t}"}).status_code == 401


def test_role_claim_must_match_database(api, world):
    t = create_access_token(world.user_a1.id, "admin")          # forged role claim
    assert api.get("/complaints", None, headers={"Authorization": f"Bearer {t}"}).status_code == 401


def test_deactivated_user_and_unknown_user_rejected(api, world, db):
    t = create_access_token(world.user_a1.id, "student")
    h = {"Authorization": f"Bearer {t}"}
    assert api.get("/notifications", None, headers=h).status_code == 200
    world.user_a1.is_active = False
    db.commit()
    assert api.get("/notifications", None, headers=h).status_code == 401
    ghost = create_access_token(uuid.uuid4(), "student")
    assert api.get("/notifications", None, headers={"Authorization": f"Bearer {ghost}"}).status_code == 401
