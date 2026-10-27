"""Module: Homework & Assignments."""
import pytest

from tests.conftest import assert_validation_error
from tests.ops.helpers import day, ids

URL = "/api/v1/assignments"


def payload(w, **overrides):
    body = {
        "section_id": str(w.section_a.id),
        "subject_id": str(w.english.id),
        "title": "Chapter 3 exercises",
        "description": "Solve questions 1 to 10.",
        "due_date": day(3),
    }
    body.update(overrides)
    return body


@pytest.fixture
def hw(client, world, h):
    """One published English assignment for section A, created by the assigned teacher."""
    r = client.post(URL, json=payload(world), headers=h(world.tu_a))
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------- creating
def test_teacher_creates_homework_and_section_is_notified(client, world, h, notes, hw):
    assert hw["teacher_id"] == str(world.t_a.id)
    assert hw["section_name"] == "Class 8-A"
    assert hw["subject_name"] == "English"
    assert hw["status"] == "published"
    assert hw["has_attachment"] is False
    # students of section A and the parent of A1 are told; nobody from section B is
    assert len(notes(world.su_a1, "homework")) == 1
    assert len(notes(world.su_a2, "homework")) == 1
    assert len(notes(world.pu_a, "homework")) == 1
    assert notes(world.su_b1) == []
    assert notes(world.pu_b) == []


def test_draft_homework_notifies_nobody(client, world, h, notes):
    r = client.post(URL, json=payload(world, status="draft"), headers=h(world.tu_a))
    assert r.status_code == 201
    assert notes(world.su_a1) == []


def test_teacher_cannot_create_for_subject_they_do_not_teach(client, world, h):
    r = client.post(URL, json=payload(world, subject_id=str(world.science.id)), headers=h(world.tu_a))
    assert r.status_code == 403


def test_teacher_cannot_create_for_another_section(client, world, h):
    r = client.post(URL, json=payload(world, section_id=str(world.section_b.id)), headers=h(world.tu_a))
    assert r.status_code == 403


def test_teacher_without_assignments_cannot_create(client, world, h):
    assert client.post(URL, json=payload(world), headers=h(world.tu_b)).status_code == 403


def test_admin_creates_homework_for_the_assigned_teacher(client, world, h):
    r = client.post(URL, json=payload(world), headers=h(world.admin))
    assert r.status_code == 201
    assert r.json()["teacher_id"] == str(world.t_a.id)


def test_admin_needs_an_assigned_teacher(client, world, h):
    r = client.post(URL, json=payload(world, subject_id=str(world.science.id)), headers=h(world.admin))
    assert r.status_code == 400


@pytest.mark.parametrize("who", ["su_a1", "pu_a"])
def test_students_and_parents_cannot_create(client, world, h, who):
    assert client.post(URL, json=payload(world), headers=h(getattr(world, who))).status_code == 403


def test_due_date_in_the_past_is_rejected(client, world, h):
    r = client.post(URL, json=payload(world, due_date=day(-1)), headers=h(world.tu_a))
    assert_validation_error(r, "due_date")


def test_short_title_is_rejected(client, world, h):
    assert_validation_error(client.post(URL, json=payload(world, title="ab"), headers=h(world.tu_a)), "title")


def test_unknown_status_is_rejected(client, world, h):
    r = client.post(URL, json=payload(world, status="closed"), headers=h(world.tu_a))
    assert_validation_error(r, "status")


# ---------------------------------------------------------------- who can see what
def test_student_sees_own_section_homework_only(client, world, h, hw):
    own = client.get(URL, headers=h(world.su_a1)).json()
    assert ids(own["items"]) == {hw["id"]}
    assert own["total"] == 1 and own["page"] == 1
    assert client.get(URL, headers=h(world.su_b1)).json()["items"] == []


def test_student_of_other_section_gets_404_on_direct_access(client, world, h, hw):
    assert client.get(f"{URL}/{hw['id']}", headers=h(world.su_b1)).status_code == 404
    assert client.get(f"{URL}/{hw['id']}", headers=h(world.su_a2)).status_code == 200


def test_parent_sees_only_their_childs_homework(client, world, h, hw):
    assert client.get(f"{URL}/{hw['id']}", headers=h(world.pu_a)).status_code == 200
    assert client.get(f"{URL}/{hw['id']}", headers=h(world.pu_b)).status_code == 404
    assert client.get(URL, headers=h(world.pu_b)).json()["items"] == []


def test_parent_can_filter_by_own_child_but_not_someone_elses(client, world, h, hw):
    ok = client.get(URL, params={"student_id": str(world.st_a1.id)}, headers=h(world.pu_a))
    assert ok.status_code == 200 and ids(ok.json()["items"]) == {hw["id"]}
    other = client.get(URL, params={"student_id": str(world.st_a1.id)}, headers=h(world.pu_b))
    assert other.status_code == 404


def test_teacher_with_no_sections_sees_nothing(client, world, h, hw):
    assert client.get(URL, headers=h(world.tu_b)).json()["items"] == []
    assert client.get(f"{URL}/{hw['id']}", headers=h(world.tu_b)).status_code == 404


def test_students_and_parents_never_see_drafts(client, world, h):
    draft = client.post(URL, json=payload(world, status="draft"), headers=h(world.tu_a)).json()
    assert client.get(URL, headers=h(world.su_a1)).json()["items"] == []
    assert client.get(f"{URL}/{draft['id']}", headers=h(world.su_a1)).status_code == 404
    assert client.get(f"{URL}/{draft['id']}", headers=h(world.pu_a)).status_code == 404
    assert client.get(f"{URL}/{draft['id']}", headers=h(world.tu_a)).status_code == 200


def test_filters_and_pagination(client, world, h):
    for n in range(3):
        client.post(URL, json=payload(world, title=f"Homework {n}", due_date=day(n + 1)), headers=h(world.tu_a))
    page = client.get(URL, params={"page_size": 2}, headers=h(world.admin)).json()
    assert page["total"] == 3 and len(page["items"]) == 2 and page["page_size"] == 2
    window = client.get(URL, params={"due_from": day(2), "due_to": day(3)}, headers=h(world.admin)).json()
    assert window["total"] == 2
    by_subject = client.get(URL, params={"subject_id": str(world.maths.id)}, headers=h(world.admin)).json()
    assert by_subject["total"] == 0
    assert client.get(URL, params={"page_size": 101}, headers=h(world.admin)).status_code == 422


# ---------------------------------------------------------------- changing and deleting
def test_owner_updates_homework(client, world, h, hw):
    r = client.patch(f"{URL}/{hw['id']}", json={"title": "Chapter 3 revised", "due_date": day(5)}, headers=h(world.tu_a))
    assert r.status_code == 200
    assert r.json()["title"] == "Chapter 3 revised" and r.json()["due_date"] == day(5)


def test_another_teacher_who_sees_it_cannot_change_it(client, world, h, add_teacher, hw):
    other, _ = add_teacher("t.sci", [(world.section_a, world.science)])
    assert client.get(f"{URL}/{hw['id']}", headers=h(other)).status_code == 200
    assert client.patch(f"{URL}/{hw['id']}", json={"title": "Hijacked"}, headers=h(other)).status_code == 403
    assert client.delete(f"{URL}/{hw['id']}", headers=h(other)).status_code == 403


def test_unrelated_teacher_gets_404_when_changing(client, world, h, hw):
    assert client.patch(f"{URL}/{hw['id']}", json={"title": "Hijacked"}, headers=h(world.tu_b)).status_code == 404


def test_students_and_parents_cannot_change_or_delete(client, world, h, hw):
    for who in (world.su_a1, world.pu_a):
        assert client.patch(f"{URL}/{hw['id']}", json={"title": "Nope nope"}, headers=h(who)).status_code == 403
        assert client.delete(f"{URL}/{hw['id']}", headers=h(who)).status_code == 403


def test_due_date_cannot_move_before_assigned_date(client, world, h, hw):
    r = client.patch(f"{URL}/{hw['id']}", json={"due_date": day(-3)}, headers=h(world.tu_a))
    assert r.status_code == 422


def test_publishing_a_draft_notifies_the_section(client, world, h, notes):
    draft = client.post(URL, json=payload(world, status="draft"), headers=h(world.tu_a)).json()
    assert notes(world.su_a1) == []
    r = client.patch(f"{URL}/{draft['id']}", json={"status": "published"}, headers=h(world.tu_a))
    assert r.status_code == 200
    assert len(notes(world.su_a1, "homework")) == 1


def test_delete_homework(client, world, h, hw):
    assert client.delete(f"{URL}/{hw['id']}", headers=h(world.tu_a)).status_code == 204
    assert client.get(f"{URL}/{hw['id']}", headers=h(world.admin)).status_code == 404


# ---------------------------------------------------------------- attachments
PDF = b"%PDF-1.4\n%test file\n"


def upload(client, headers, assignment_id, name="worksheet.pdf", content=PDF):
    return client.post(f"{URL}/{assignment_id}/attachment", files={"file": (name, content, "application/octet-stream")}, headers=headers)


def test_upload_and_download_attachment(client, world, h, hw):
    r = upload(client, h(world.tu_a), hw["id"])
    assert r.status_code == 200 and r.json()["has_attachment"] is True
    got = client.get(f"{URL}/{hw['id']}/attachment", headers=h(world.su_a1))
    assert got.status_code == 200 and got.content == PDF


def test_attachment_is_private_to_the_section(client, world, h, hw):
    upload(client, h(world.tu_a), hw["id"])
    assert client.get(f"{URL}/{hw['id']}/attachment", headers=h(world.su_b1)).status_code == 404
    assert client.get(f"{URL}/{hw['id']}/attachment", headers=h(world.pu_b)).status_code == 404
    assert client.get(f"{URL}/{hw['id']}/attachment", headers=h(world.pu_a)).status_code == 200


def test_download_without_attachment_is_404(client, world, h, hw):
    assert client.get(f"{URL}/{hw['id']}/attachment", headers=h(world.su_a1)).status_code == 404


def test_students_cannot_upload(client, world, h, hw):
    assert upload(client, h(world.su_a1), hw["id"]).status_code == 403


def test_disallowed_extension_is_rejected(client, world, h, hw):
    assert upload(client, h(world.tu_a), hw["id"], name="run.exe", content=b"MZ\x90\x00").status_code == 400


def test_content_must_match_extension(client, world, h, hw):
    assert upload(client, h(world.tu_a), hw["id"], name="fake.pdf", content=b"just some text").status_code == 400


def test_oversized_file_is_rejected(client, world, h, hw):
    big = b"%PDF" + b"0" * (1024 * 1024)  # MAX_UPLOAD_MB=1 in tests/_env.py
    assert upload(client, h(world.tu_a), hw["id"], content=big).status_code == 413


def test_path_traversal_in_filename_is_harmless(client, world, h, hw):
    r = upload(client, h(world.tu_a), hw["id"], name="../../evil.pdf")
    assert r.status_code == 200
    assert client.get(f"{URL}/{hw['id']}/attachment", headers=h(world.su_a1)).status_code == 200


# ---------------------------------------------------------------- student submission is disabled
@pytest.mark.parametrize("path", ["submissions", "submit"])
def test_student_submission_endpoints_do_not_exist(client, world, h, hw, path):
    r = client.post(f"{URL}/{hw['id']}/{path}", json={}, headers=h(world.su_a1))
    assert r.status_code in (404, 405)
