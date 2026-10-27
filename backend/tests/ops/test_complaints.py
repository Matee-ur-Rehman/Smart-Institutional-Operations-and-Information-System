"""Module: Complaints & Feedback (parents submit, admin manages, other families see nothing)."""
import pytest

from tests.conftest import assert_validation_error
from tests.ops.helpers import ids

URL = "/api/v1/complaints"


def body(w, **overrides):
    data = {
        "student_id": str(w.st_a1.id),
        "category": "facility",
        "kind": "complaint",
        "subject": "Broken classroom fan",
        "description": "The fan in Class 8-A has not worked for two weeks.",
    }
    data.update(overrides)
    return data


@pytest.fixture
def ticket(client, world, h):
    r = client.post(URL, json=body(world), headers=h(world.pu_a))
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------- submitting
def test_parent_submits_and_admin_is_notified(client, world, h, notes, ticket):
    assert ticket["ticket_no"].startswith("TKT-") and ticket["status"] == "open" and ticket["priority"] == "normal"
    assert ticket["student_name"] == "Ali Raza" and ticket["submitter_name"] == "Parent of A1" and ticket["comments"] == []
    assert len(notes(world.admin, "complaint")) == 1


def test_feedback_without_a_student(client, world, h):
    r = client.post(URL, json=body(world, student_id=None, kind="suggestion", category="other"), headers=h(world.pu_a))
    assert r.status_code == 201 and r.json()["student_id"] is None and r.json()["kind"] == "suggestion"


def test_parent_cannot_file_about_someone_elses_child(client, world, h):
    assert client.post(URL, json=body(world, student_id=str(world.st_b1.id)), headers=h(world.pu_a)).status_code == 404


@pytest.mark.parametrize("who", ["su_a1", "tu_a", "admin"])
def test_only_parents_submit(client, world, h, who):
    assert client.post(URL, json=body(world), headers=h(getattr(world, who))).status_code == 403


def test_validation(client, world, h):
    parent = h(world.pu_a)
    assert_validation_error(client.post(URL, json=body(world, description="too short"), headers=parent), "description")
    assert_validation_error(client.post(URL, json=body(world, subject="ab"), headers=parent), "subject")
    assert_validation_error(client.post(URL, json=body(world, category="gossip"), headers=parent), "category")
    assert_validation_error(client.post(URL, json=body(world, kind="rant"), headers=parent), "kind")


# ---------------------------------------------------------------- who sees which ticket
def test_parent_sees_only_own_tickets(client, world, h, ticket):
    other = client.post(URL, json=body(world, student_id=str(world.st_b1.id), subject="Late bus"), headers=h(world.pu_b)).json()
    assert ids(client.get(URL, headers=h(world.pu_a)).json()["items"]) == {ticket["id"]}
    assert ids(client.get(URL, headers=h(world.pu_b)).json()["items"]) == {other["id"]}
    assert ids(client.get(URL, headers=h(world.admin)).json()["items"]) == {ticket["id"], other["id"]}


def test_another_family_gets_404_on_everything(client, world, h, ticket):
    headers = h(world.pu_b)
    assert client.get(f"{URL}/{ticket['id']}", headers=headers).status_code == 404
    assert client.post(f"{URL}/{ticket['id']}/comments", json={"message": "Can I read this?"}, headers=headers).status_code == 404


def test_parent_cannot_change_status_or_priority(client, world, h, ticket):
    r = client.patch(f"{URL}/{ticket['id']}", json={"status": "resolved"}, headers=h(world.pu_a))
    assert r.status_code == 403
    assert client.get(f"{URL}/{ticket['id']}", headers=h(world.pu_a)).json()["status"] == "open"


@pytest.mark.parametrize("who", ["tu_a", "su_a1"])
def test_teachers_and_students_cannot_read_tickets(client, world, h, ticket, who):
    assert client.get(f"{URL}/{ticket['id']}", headers=h(getattr(world, who))).status_code == 403
    assert client.get(f"{URL}/summary", headers=h(getattr(world, who))).status_code == 403


def test_filters(client, world, h, ticket):
    client.post(URL, json=body(world, category="fee", kind="feedback", subject="Fee slip format"), headers=h(world.pu_a))
    admin = h(world.admin)
    assert client.get(URL, params={"category": "fee"}, headers=admin).json()["total"] == 1
    assert client.get(URL, params={"kind": "feedback"}, headers=admin).json()["total"] == 1
    assert client.get(URL, params={"status": "open"}, headers=admin).json()["total"] == 2
    assert client.get(URL, params={"status": "closed"}, headers=admin).json()["total"] == 0
    assert client.get(URL, params={"status": "invalid"}, headers=admin).status_code == 422


# ---------------------------------------------------------------- tracking
def test_status_change_notifies_the_parent(client, world, h, notes, ticket):
    r = client.patch(f"{URL}/{ticket['id']}", json={"status": "in_review", "priority": "high"}, headers=h(world.admin))
    assert r.status_code == 200 and r.json()["status"] == "in_review" and r.json()["priority"] == "high"
    assert len(notes(world.pu_a, "complaint")) == 1
    client.patch(f"{URL}/{ticket['id']}", json={"priority": "low"}, headers=h(world.admin))
    assert len(notes(world.pu_a, "complaint")) == 1  # no status change, no new notification


def test_assignment_only_to_an_admin(client, world, h, ticket):
    admin = h(world.admin)
    assert client.patch(f"{URL}/{ticket['id']}", json={"assigned_to": str(world.tu_a.id)}, headers=admin).status_code == 400
    ok = client.patch(f"{URL}/{ticket['id']}", json={"assigned_to": str(world.admin.id)}, headers=admin)
    assert ok.status_code == 200 and ok.json()["assigned_to"] == str(world.admin.id)
    assert client.get(URL, params={"assigned_to": str(world.admin.id)}, headers=admin).json()["total"] == 1


def test_invalid_status_is_rejected(client, world, h, ticket):
    assert client.patch(f"{URL}/{ticket['id']}", json={"status": "vanished"}, headers=h(world.admin)).status_code == 422
    assert client.patch(f"{URL}/{ticket['id']}", json={"status": None}, headers=h(world.admin)).status_code == 422


def test_internal_notes_stay_hidden_from_the_parent(client, world, h, notes, ticket):
    admin, parent = h(world.admin), h(world.pu_a)
    client.post(f"{URL}/{ticket['id']}/comments", json={"message": "Parent is often late with fees.", "is_internal": True}, headers=admin)
    assert notes(world.pu_a, "complaint") == []  # internal notes never notify
    client.post(f"{URL}/{ticket['id']}/comments", json={"message": "We are fixing the fan this week."}, headers=admin)
    assert len(notes(world.pu_a, "complaint")) == 1

    parent_view = client.get(f"{URL}/{ticket['id']}", headers=parent).json()
    assert [c["message"] for c in parent_view["comments"]] == ["We are fixing the fan this week."]
    admin_view = client.get(f"{URL}/{ticket['id']}", headers=admin).json()
    assert len(admin_view["comments"]) == 2 and admin_view["comments"][0]["is_internal"] is True


def test_parent_cannot_write_internal_notes(client, world, h, ticket):
    r = client.post(f"{URL}/{ticket['id']}/comments", json={"message": "Secret", "is_internal": True}, headers=h(world.pu_a))
    assert r.status_code == 403


def test_parent_reply_notifies_the_assigned_admin(client, world, h, notes, ticket):
    client.patch(f"{URL}/{ticket['id']}", json={"assigned_to": str(world.admin.id)}, headers=h(world.admin))
    before = len(notes(world.admin, "complaint"))
    r = client.post(f"{URL}/{ticket['id']}/comments", json={"message": "Any update on this?"}, headers=h(world.pu_a))
    assert r.status_code == 201 and r.json()["author_role"] == "parent"
    assert len(notes(world.admin, "complaint")) == before + 1


def test_closed_tickets_take_no_more_parent_replies(client, world, h, ticket):
    client.patch(f"{URL}/{ticket['id']}", json={"status": "closed"}, headers=h(world.admin))
    assert client.post(f"{URL}/{ticket['id']}/comments", json={"message": "One more thing"}, headers=h(world.pu_a)).status_code == 409
    assert client.post(f"{URL}/{ticket['id']}/comments", json={"message": "Admin note"}, headers=h(world.admin)).status_code == 201


def test_summary(client, world, h, ticket):
    client.post(URL, json=body(world, category="fee"), headers=h(world.pu_a))
    client.patch(f"{URL}/{ticket['id']}", json={"status": "resolved"}, headers=h(world.admin))
    s = client.get(f"{URL}/summary", headers=h(world.admin)).json()
    assert s["total"] == 2
    assert s["by_status"] == {"resolved": 1, "open": 1}
    assert s["by_category"] == {"facility": 1, "fee": 1}
