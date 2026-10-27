"""Modules: Announcements & Notifications (the in-app inbox works without Firebase)."""
from datetime import datetime, timedelta, timezone

from app.modules.announcements.models import Announcement
from app.modules.notifications.models import DeviceToken
from app.modules.notifications.service import notify_users
from tests.conftest import assert_validation_error
from tests.ops.helpers import ids

ANN = "/api/v1/announcements"
NOTES = "/api/v1/notifications"


def announce(client, headers, **overrides):
    body = {"title": "School closed on Friday", "body": "The school will remain closed on Friday.", "audience": "all"}
    body.update(overrides)
    return client.post(ANN, json=body, headers=headers)


# ---------------------------------------------------------------- announcements
def test_published_announcement_reaches_every_active_user(client, world, h, notes):
    r = announce(client, h(world.admin))
    assert r.status_code == 201 and r.json()["status"] == "published" and r.json()["publish_at"]
    for user in (world.tu_a, world.tu_b, world.su_a1, world.su_a2, world.su_b1, world.pu_a, world.pu_b, world.admin):
        assert len(notes(user, "announcement")) == 1, user.full_name
    assert ids(client.get(ANN, headers=h(world.su_a1)).json()["items"]) == {r.json()["id"]}


def test_push_is_disabled_without_firebase(client, world, h, notes):
    announce(client, h(world.admin))
    assert {n.push_status for n in notes(world.su_a1)} == {"disabled"}


def test_deactivated_users_are_not_notified(client, db, world, h, notes):
    world.su_b1.is_active = False
    db.commit()
    announce(client, h(world.admin))
    assert notes(world.su_b1) == []


def test_draft_is_invisible_until_published(client, world, h, notes):
    draft = announce(client, h(world.admin), status="draft").json()
    assert draft["status"] == "draft" and draft["publish_at"] is None
    assert client.get(ANN, headers=h(world.su_a1)).json()["items"] == []
    assert client.get(f"{ANN}/{draft['id']}", headers=h(world.su_a1)).status_code == 404
    assert notes(world.su_a1) == []
    assert ids(client.get(ANN, params={"status": "draft"}, headers=h(world.admin)).json()["items"]) == {draft["id"]}

    assert client.post(f"{ANN}/{draft['id']}/publish", headers=h(world.admin)).status_code == 200
    assert client.get(f"{ANN}/{draft['id']}", headers=h(world.su_a1)).status_code == 200
    assert len(notes(world.su_a1, "announcement")) == 1
    assert client.post(f"{ANN}/{draft['id']}/publish", headers=h(world.admin)).status_code == 409  # not notified twice


def test_audiences(client, world, h):
    admin = h(world.admin)
    parents = announce(client, admin, title="Parents meeting", audience="parents").json()
    teachers = announce(client, admin, title="Staff notice", audience="teachers").json()
    students = announce(client, admin, title="Students notice", audience="students").json()
    assert ids(client.get(ANN, headers=h(world.pu_a)).json()["items"]) == {parents["id"]}
    assert ids(client.get(ANN, headers=h(world.tu_a)).json()["items"]) == {teachers["id"]}
    assert ids(client.get(ANN, headers=h(world.su_a1)).json()["items"]) == {students["id"]}
    assert client.get(f"{ANN}/{teachers['id']}", headers=h(world.pu_a)).status_code == 404


def test_section_and_class_audiences(client, world, h, notes):
    admin = h(world.admin)
    only_a = announce(client, admin, title="Section A only", audience="class", section_id=str(world.section_a.id)).json()
    whole_8 = announce(client, admin, title="Class 8 notice", audience="class", class_id=str(world.class_8.id)).json()
    class_9 = announce(client, admin, title="Class 9 notice", audience="class", class_id=str(world.class_9.id)).json()
    assert ids(client.get(ANN, headers=h(world.su_a1)).json()["items"]) == {only_a["id"], whole_8["id"]}
    assert ids(client.get(ANN, headers=h(world.su_b1)).json()["items"]) == {whole_8["id"]}
    assert ids(client.get(ANN, headers=h(world.pu_b)).json()["items"]) == {whole_8["id"]}
    assert client.get(f"{ANN}/{only_a['id']}", headers=h(world.su_b1)).status_code == 404
    assert client.get(f"{ANN}/{class_9['id']}", headers=h(world.su_a1)).status_code == 404
    assert len(notes(world.su_a1, "announcement")) == 2 and len(notes(world.su_b1, "announcement")) == 1


def test_expired_announcements_disappear(client, db, world, h):
    created = announce(client, h(world.admin), expires_at=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat()).json()
    assert client.get(f"{ANN}/{created['id']}", headers=h(world.su_a1)).status_code == 200
    row = db.get(Announcement, __import__("uuid").UUID(created["id"]))
    row.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    assert client.get(ANN, headers=h(world.su_a1)).json()["items"] == []
    assert client.get(f"{ANN}/{created['id']}", headers=h(world.su_a1)).status_code == 404
    assert client.get(f"{ANN}/{created['id']}", headers=h(world.admin)).status_code == 200


def test_archive_hides_from_readers(client, world, h):
    created = announce(client, h(world.admin)).json()
    assert client.post(f"{ANN}/{created['id']}/archive", headers=h(world.admin)).json()["status"] == "archived"
    assert client.get(ANN, headers=h(world.su_a1)).json()["items"] == []
    assert client.get(ANN, params={"status": "archived"}, headers=h(world.admin)).json()["total"] == 1


def test_announcement_validation(client, world, h):
    admin = h(world.admin)
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert_validation_error(announce(client, admin, expires_at=past))
    assert_validation_error(announce(client, admin, audience="class"))
    assert_validation_error(announce(client, admin, class_id=str(world.class_8.id)))
    assert_validation_error(announce(client, admin, priority="whenever"), "priority")
    assert_validation_error(announce(client, admin, title="x"), "title")


def test_only_admin_manages_announcements(client, world, h):
    created = announce(client, h(world.admin)).json()
    for who in (world.tu_a, world.su_a1, world.pu_a):
        headers = h(who)
        assert announce(client, headers).status_code == 403
        assert client.patch(f"{ANN}/{created['id']}", json={"title": "Changed title"}, headers=headers).status_code == 403
        assert client.post(f"{ANN}/{created['id']}/archive", headers=headers).status_code == 403
        assert client.delete(f"{ANN}/{created['id']}", headers=headers).status_code == 403


def test_readers_cannot_use_the_status_filter_to_see_drafts(client, world, h):
    announce(client, h(world.admin), status="draft")
    assert client.get(ANN, params={"status": "draft"}, headers=h(world.su_a1)).json()["items"] == []


# ---------------------------------------------------------------- notification inbox
def test_inbox_is_private(client, world, h):
    announce(client, h(world.admin))
    mine = client.get(NOTES, headers=h(world.su_a1)).json()
    assert mine["total"] == 1
    other = client.get(NOTES, headers=h(world.su_b1)).json()
    assert other["total"] == 1 and ids(other["items"]).isdisjoint(ids(mine["items"]))


def test_read_state_and_unread_count(client, world, h):
    announce(client, h(world.admin), title="First notice")
    announce(client, h(world.admin), title="Second notice")
    headers = h(world.su_a1)
    assert client.get(f"{NOTES}/unread-count", headers=headers).json() == {"count": 2}
    first = client.get(NOTES, headers=headers).json()["items"][0]
    done = client.post(f"{NOTES}/{first['id']}/read", headers=headers).json()
    assert done["is_read"] is True and done["read_at"]
    assert client.get(f"{NOTES}/unread-count", headers=headers).json() == {"count": 1}
    assert client.get(NOTES, params={"is_read": False}, headers=headers).json()["total"] == 1
    assert client.post(f"{NOTES}/read-all", headers=headers).json() == {"updated": 1}
    assert client.get(f"{NOTES}/unread-count", headers=headers).json() == {"count": 0}


def test_cannot_mark_someone_elses_notification(client, world, h):
    announce(client, h(world.admin))
    theirs = client.get(NOTES, headers=h(world.su_b1)).json()["items"][0]
    assert client.post(f"{NOTES}/{theirs['id']}/read", headers=h(world.su_a1)).status_code == 404
    assert client.get(f"{NOTES}/unread-count", headers=h(world.su_b1)).json() == {"count": 1}


def test_read_all_only_touches_own_notifications(client, world, h):
    announce(client, h(world.admin))
    client.post(f"{NOTES}/read-all", headers=h(world.su_a1))
    assert client.get(f"{NOTES}/unread-count", headers=h(world.su_b1)).json() == {"count": 1}


def test_type_filter(client, world, h):
    announce(client, h(world.admin))
    assert client.get(NOTES, params={"type": "announcement"}, headers=h(world.su_a1)).json()["total"] == 1
    assert client.get(NOTES, params={"type": "fee"}, headers=h(world.su_a1)).json()["total"] == 0


# ---------------------------------------------------------------- device tokens (stored, used only when FCM is on)
TOKEN = "fcm-token-1234567890-abcdef"


def test_register_and_move_device_token(client, db, world, h):
    assert client.post("/api/v1/devices/register", json={"token": TOKEN, "platform": "android"}, headers=h(world.pu_a)).status_code == 201
    # the same phone signs in as someone else: the token follows the latest user, no duplicate row
    assert client.post("/api/v1/devices/register", json={"token": TOKEN, "platform": "android"}, headers=h(world.pu_b)).status_code == 201
    rows = db.query(DeviceToken).all()
    assert len(rows) == 1 and rows[0].user_id == world.pu_b.id


def test_unregister_only_own_token(client, db, world, h):
    client.post("/api/v1/devices/register", json={"token": TOKEN, "platform": "android"}, headers=h(world.pu_a))
    client.delete(f"/api/v1/devices/{TOKEN}", headers=h(world.pu_b))
    assert db.query(DeviceToken).count() == 1
    assert client.delete(f"/api/v1/devices/{TOKEN}", headers=h(world.pu_a)).status_code == 204
    db.expire_all()
    assert db.query(DeviceToken).count() == 0


def test_bad_device_registration(client, world, h):
    assert client.post("/api/v1/devices/register", json={"token": "short", "platform": "android"}, headers=h(world.pu_a)).status_code == 422
    assert client.post("/api/v1/devices/register", json={"token": TOKEN, "platform": "ios"}, headers=h(world.pu_a)).status_code == 422


# ---------------------------------------------------------------- the function Member 1 will call
def test_notify_users_dedupes_and_never_commits(db, world, notes):
    count = notify_users(db, [world.su_a1.id, world.su_a1.id, world.pu_a.id], "Leave approved", "Your request was approved.", "leave")
    assert count == 2
    assert len(notes(world.su_a1, "leave")) == 1
    db.rollback()  # the caller owns the transaction: if it rolls back, the notifications vanish
    assert notes(world.su_a1, "leave") == []


def test_notify_users_with_nobody_is_a_noop(db):
    assert notify_users(db, [], "Title", "Body", "system") == 0


def test_attendance_and_leave_types_are_allowed(db, world, notes):
    """Faizan's modules use these two types (docs/API_CONTRACT.md section 5)."""
    assert notify_users(db, [world.pu_a.id], "Absent today", "Ali was marked absent.", "attendance") == 1
    assert notify_users(db, [world.pu_a.id], "Leave decision", "Approved.", "leave") == 1
    db.commit()
    assert len(notes(world.pu_a)) == 2
