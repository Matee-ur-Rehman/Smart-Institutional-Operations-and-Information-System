import uuid

from app.modules.notifications import push
from app.modules.notifications.models import DeviceToken, Notification
from app.modules.notifications.service import notify_section, notify_users

N = "/notifications"


def test_notify_users_creates_rows_without_commit(db, world):
    n = notify_users(db, [world.user_a1.id, world.user_a1.id, None], "Hello", "Body", "system")
    assert n == 1
    db.rollback()
    assert db.query(Notification).count() == 0       # never commits on its own


def test_notify_skips_inactive_users(db, world):
    world.user_a1.is_active = False
    db.flush()
    assert notify_users(db, [world.user_a1.id, world.user_a2.id], "T", "B", "system") == 1
    assert notify_users(db, [], "T", "B", "system") == 0


def test_notify_section_roles(db, world):
    w = world
    n = notify_section(db, w.sec_a.id, "T", "B", "homework")           # students + parents by default
    db.commit()
    got = {x.user_id for x in db.query(Notification).all()}
    assert n == len(got)
    assert {w.user_a1.id, w.user_a2.id, w.user_a3.id, w.up1.id} <= got
    assert w.ua.id not in got and w.user_b1.id not in got and w.up2.id not in got
    db.query(Notification).delete()
    notify_section(db, w.sec_a.id, "T", "B", "system", include_parents=False, include_students=False, include_teachers=True)
    db.commit()
    assert {x.user_id for x in db.query(Notification).all()} == {w.ua.id}


def test_push_disabled_status(db, world):
    assert push.fcm_ready() is False and push.initial_push_status() == "disabled"
    notify_users(db, [world.user_a1.id], "T", "B", "system")
    db.commit()
    assert db.query(Notification).one().push_status == "disabled"
    assert db.info.get("pending_push") is None


def test_push_enabled_without_credentials_is_off(monkeypatch):
    monkeypatch.setattr(push.settings, "FCM_ENABLED", True)
    monkeypatch.setattr(push.settings, "FCM_CREDENTIALS_FILE", "/nonexistent.json")
    assert push.fcm_ready() is False


def test_send_pending_with_fake_sender(db, world, monkeypatch):
    w = world
    sent = []

    def fake(token, title, body, data):
        if token == "bad-token-0000":
            raise RuntimeError("unregistered")
        sent.append((token, title))

    monkeypatch.setattr(push, "_send_one", fake)
    db.add_all([DeviceToken(user_id=w.user_a1.id, token="good-token-0001", platform="android"),
                DeviceToken(user_id=w.user_a2.id, token="bad-token-0000", platform="android")])
    ns = [Notification(user_id=u.id, title="T", body="B", type="system", push_status="queued")
          for u in (w.user_a1, w.user_a2, w.user_a3)]
    db.add_all(ns)
    db.commit()
    push.send_pending([n.id for n in ns])
    db.expire_all()
    st = {n.user_id: n.push_status for n in db.query(Notification).all()}
    assert st[w.user_a1.id] == "sent" and st[w.user_a2.id] == "failed" and st[w.user_a3.id] == "failed"
    assert sent == [("good-token-0001", "T")]


def test_inbox_isolation_and_read_flow(api, world, db):
    w = world
    notify_users(db, [w.user_a1.id], "For A1", "b", "system")
    notify_users(db, [w.user_a2.id], "For A2", "b", "system")
    notify_users(db, [w.user_a1.id], "Second", "b", "homework")
    db.commit()
    r = api.get(N, w.user_a1).json()
    assert r["total"] == 2 and {i["title"] for i in r["items"]} == {"For A1", "Second"}
    assert api.get(N + "/unread-count", w.user_a1).json() == {"count": 2}
    assert api.get(N + "?type=homework", w.user_a1).json()["total"] == 1
    nid = r["items"][0]["id"]
    assert api.post(f"{N}/{nid}/read", w.user_a2).status_code == 404          # someone else's
    assert api.post(f"{N}/{nid}/read", w.user_a1).json()["is_read"] is True
    assert api.get(N + "/unread-count", w.user_a1).json() == {"count": 1}
    assert api.get(N + "?is_read=false", w.user_a1).json()["total"] == 1
    assert api.get(N + "?is_read=true", w.user_a1).json()["total"] == 1
    assert api.post(f"{N}/read-all", w.user_a1).json() == {"updated": 1}
    assert api.get(N + "/unread-count", w.user_a1).json() == {"count": 0}
    assert api.get(N + "/unread-count", w.user_a2).json() == {"count": 1}       # untouched


def test_mark_read_bad_ids(api, world):
    assert api.post(f"{N}/not-a-uuid/read", world.user_a1).status_code == 404
    assert api.post(f"{N}/{uuid.uuid4()}/read", world.user_a1).status_code == 404


def test_device_register_unregister(api, world, db):
    w = world
    tok = "fcm-token-abcdefghij"
    assert api.post("/devices/register", w.user_a1, json={"token": tok, "platform": "android"}).status_code == 201
    assert api.post("/devices/register", w.user_a1, json={"token": tok, "platform": "android"}).status_code == 201
    assert db.query(DeviceToken).count() == 1
    # same device, different login: token moves to the new user
    assert api.post("/devices/register", w.up1, json={"token": tok, "platform": "web"}).status_code == 201
    db.expire_all()
    d = db.query(DeviceToken).one()
    assert d.user_id == w.up1.id and d.platform == "web"
    assert api.delete(f"/devices/{tok}", w.user_a1).status_code == 404        # not theirs any more
    assert api.delete(f"/devices/{tok}", w.up1).status_code == 204
    assert db.query(DeviceToken).count() == 0
    assert api.post("/devices/register", w.up1, json={"token": "short", "platform": "android"}).status_code == 422
    assert api.post("/devices/register", w.up1, json={"token": tok, "platform": "ios"}).status_code == 422
