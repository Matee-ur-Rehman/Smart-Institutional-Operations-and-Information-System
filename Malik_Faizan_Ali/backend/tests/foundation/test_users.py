"""User administration."""
from tests.conftest import PASSWORD
from tests.foundation.test_auth import login


def test_admin_only(api, world):
    w = world
    for u in (w.ua, w.user_a1, w.up1):
        assert api.get("/users", u).status_code == 403
        assert api.post("/users", u, json={"login_id": "x.admin", "full_name": "X Admin"}).status_code == 403
        assert api.patch(f"/users/{w.admin.id}", u, json={"full_name": "Hack"}).status_code == 403
        assert api.post(f"/users/{w.admin.id}/reset-password", u).status_code == 403
    assert api.get("/users", None).status_code == 401


def test_list_filters_and_search(api, world):
    w = world
    assert api.get("/users", w.admin).json()["total"] == 1 + 3 + 6 + 2
    assert api.get("/users?role=teacher", w.admin).json()["total"] == 3
    assert api.get("/users?q=Danish", w.admin).json()["total"] == 1
    assert api.get("/users?q=t.a", w.admin).json()["total"] >= 1
    assert api.get("/users?role=boss", w.admin).status_code == 422
    row = api.get("/users?role=teacher&q=Teacher A", w.admin).json()["items"][0]
    assert row["profile_id"] == str(w.teacher_a.id) and "password_hash" not in row


def test_create_admin_with_temp_password(api, world):
    w = world
    r = api.post("/users", w.admin, json={"login_id": "office.admin", "full_name": "Office Admin", "email": "office@example.com"})
    assert r.status_code == 201
    temp = r.json()["temporary_password"]
    assert temp and r.json()["user"]["must_change_password"] is True
    assert login(api, "office.admin", temp).status_code == 200
    assert api.post("/users", w.admin, json={"login_id": "office.admin", "full_name": "Dup"}).status_code == 409
    assert api.post("/users", w.admin, json={"login_id": "bad id!", "full_name": "Bad Id"}).status_code == 422
    assert api.post("/users", w.admin, json={"login_id": "x.admin2", "full_name": "Weak", "password": "weakpass"}).status_code == 422
    assert api.post("/users", w.admin, json={"login_id": "x.admin3", "full_name": "Role Escalate", "role": "teacher"}).status_code == 422
    chosen = api.post("/users", w.admin, json={"login_id": "x.admin4", "full_name": "Chosen Pw", "password": "Chosen123"})
    assert chosen.status_code == 201 and chosen.json()["temporary_password"] is None


def test_deactivation_rules(api, world, db):
    w = world
    assert api.patch(f"/users/{w.admin.id}", w.admin, json={"is_active": False}).status_code == 400          # self / last admin
    second = api.post("/users", w.admin, json={"login_id": "second.admin", "full_name": "Second Admin"}).json()["user"]
    assert api.patch(f"/users/{w.admin.id}", w.admin, json={"is_active": False}).status_code == 400          # still self
    # teacher + student deactivation syncs the profile rows used by access checks
    s = login(api, "t.a").json()
    assert api.patch(f"/users/{w.ua.id}", w.admin, json={"is_active": False}).status_code == 200
    db.expire_all()
    assert db.get(type(w.teacher_a), w.teacher_a.id).is_active is False
    assert login(api, "t.a").status_code == 401
    assert api.post("/auth/refresh", None, json={"refresh_token": s["refresh_token"]}).status_code == 401
    assert api.patch(f"/users/{w.user_a1.id}", w.admin, json={"is_active": False}).status_code == 200
    db.expire_all()
    assert db.get(type(w.a1), w.a1.id).is_active is False
    assert api.patch(f"/users/{w.ua.id}", w.admin, json={"is_active": True}).status_code == 200
    assert api.patch(f"/users/{second['id']}", w.admin, json={"is_active": False}).status_code == 200      # not the last admin: ok


def test_update_validation_and_unknown(api, world):
    w = world
    assert api.patch(f"/users/{w.ua.id}", w.admin, json={"phone": "x"}).status_code == 422
    assert api.patch(f"/users/{w.ua.id}", w.admin, json={"email": "t.a@example.com"}).status_code == 200
    assert api.patch(f"/users/{w.ub.id}", w.admin, json={"email": "t.a@example.com"}).status_code == 409
    assert api.patch(f"/users/{w.ua.id}", w.admin, json={"role": "admin"}).json()["role"] == "teacher"          # role is immutable here
    assert api.get("/users/00000000-0000-0000-0000-000000000000", w.admin).status_code == 404
    assert api.get("/users/not-a-uuid", w.admin).status_code == 422


def test_reset_password(api, world):
    w = world
    r = api.post(f"/users/{w.user_a1.id}/reset-password", w.admin)
    assert r.status_code == 200 and r.json()["temporary_password"]
    assert login(api, "s.a1", PASSWORD, "mobile").status_code == 401
    assert login(api, "s.a1", r.json()["temporary_password"], "mobile").json()["user"]["must_change_password"] is True
    r = api.post(f"/users/{w.user_a1.id}/reset-password", w.admin, json={"new_password": "Chosen456"})
    assert r.status_code == 200 and r.json()["temporary_password"] is None
    assert login(api, "s.a1", "Chosen456", "mobile").status_code == 200
    assert api.post(f"/users/{w.user_a1.id}/reset-password", w.admin, json={"new_password": "weak"}).status_code == 422
