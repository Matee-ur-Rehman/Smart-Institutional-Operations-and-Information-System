"""Module: Timetable."""
import pytest

from app.modules.ops_common.core_refs import TeacherAssignment
from tests.conftest import assert_validation_error

BASE = "/api/v1"


@pytest.fixture
def periods(client, world, h):
    admin = h(world.admin)
    out = []
    for no, label, start, end, brk in [
        (1, "Period 1", "08:00", "08:40", False),
        (2, "Period 2", "08:40", "09:20", False),
        (3, "Break", "09:20", "09:40", True),
    ]:
        r = client.post(
            f"{BASE}/period-definitions",
            json={"period_no": no, "label": label, "start_time": start, "end_time": end, "is_break": brk},
            headers=admin,
        )
        assert r.status_code == 201, r.text
        out.append(r.json())
    return out


def slot_body(w, periods, subject=None, section=None, day=1, period=0, **extra):
    return {
        "section_id": str((section or w.section_a).id),
        "subject_id": str((subject or w.english).id),
        "day_of_week": day,
        "period_id": periods[period]["id"],
        **extra,
    }


@pytest.fixture
def slot(client, world, h, periods):
    r = client.post(f"{BASE}/timetable-slots", json=slot_body(world, periods), headers=h(world.admin))
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------- periods
def test_period_validation(client, world, h, periods):
    admin = h(world.admin)
    clash = {"period_no": 5, "label": "Odd", "start_time": "08:30", "end_time": "09:00"}
    assert client.post(f"{BASE}/period-definitions", json=clash, headers=admin).status_code == 409  # overlaps
    dup = {"period_no": 1, "label": "Again", "start_time": "13:00", "end_time": "13:40"}
    assert client.post(f"{BASE}/period-definitions", json=dup, headers=admin).status_code == 409
    backwards = {"period_no": 6, "label": "Bad", "start_time": "14:00", "end_time": "13:00"}
    assert_validation_error(client.post(f"{BASE}/period-definitions", json=backwards, headers=admin))


def test_everyone_can_read_periods(client, world, h, periods):
    for who in (world.tu_a, world.su_a1, world.pu_a):
        assert len(client.get(f"{BASE}/period-definitions", headers=h(who)).json()) == 3


def test_period_in_use_cannot_be_deleted(client, world, h, periods, slot):
    assert client.delete(f"{BASE}/period-definitions/{periods[0]['id']}", headers=h(world.admin)).status_code == 409
    assert client.delete(f"{BASE}/period-definitions/{periods[1]['id']}", headers=h(world.admin)).status_code == 204


# ---------------------------------------------------------------- creating lessons
def test_lesson_takes_the_assigned_teacher(slot, world):
    assert slot["teacher_id"] == str(world.t_a.id) and slot["teacher_name"] == "Ahmed Khan"
    assert slot["section_name"] == "Class 8-A" and slot["subject_name"] == "English" and slot["period_no"] == 1


def test_section_cannot_have_two_lessons_in_one_period(client, world, h, periods, slot):
    r = client.post(f"{BASE}/timetable-slots", json=slot_body(world, periods, subject=world.maths), headers=h(world.admin))
    assert r.status_code == 409


def test_teacher_cannot_be_in_two_sections_at_once(client, world, h, db, periods, slot):
    db.add(TeacherAssignment(teacher_id=world.t_a.id, section_id=world.section_b.id, subject_id=world.science.id, academic_year_id=world.year.id))
    db.commit()
    r = client.post(
        f"{BASE}/timetable-slots",
        json=slot_body(world, periods, subject=world.science, section=world.section_b),
        headers=h(world.admin),
    )
    assert r.status_code == 409
    other_period = slot_body(world, periods, subject=world.science, section=world.section_b, period=1)
    assert client.post(f"{BASE}/timetable-slots", json=other_period, headers=h(world.admin)).status_code == 201


def test_break_periods_cannot_hold_lessons(client, world, h, periods):
    r = client.post(f"{BASE}/timetable-slots", json=slot_body(world, periods, period=2), headers=h(world.admin))
    assert r.status_code == 400


def test_subject_without_assigned_teacher_is_refused(client, world, h, periods):
    r = client.post(f"{BASE}/timetable-slots", json=slot_body(world, periods, subject=world.science), headers=h(world.admin))
    assert r.status_code == 400


def test_explicit_teacher_must_actually_teach_it(client, world, h, periods):
    r = client.post(
        f"{BASE}/timetable-slots", json=slot_body(world, periods, teacher_id=str(world.t_b.id)), headers=h(world.admin)
    )
    assert r.status_code == 400


def test_day_of_week_is_validated(client, world, h, periods):
    for bad in (0, 7):
        assert_validation_error(
            client.post(f"{BASE}/timetable-slots", json=slot_body(world, periods, day=bad), headers=h(world.admin)), "day_of_week"
        )


@pytest.mark.parametrize("who", ["tu_a", "su_a1", "pu_a"])
def test_only_admin_edits_the_timetable(client, world, h, periods, slot, who):
    headers = h(getattr(world, who))
    assert client.post(f"{BASE}/timetable-slots", json=slot_body(world, periods, day=2), headers=headers).status_code == 403
    assert client.patch(f"{BASE}/timetable-slots/{slot['id']}", json={"day_of_week": 3}, headers=headers).status_code == 403
    assert client.delete(f"{BASE}/timetable-slots/{slot['id']}", headers=headers).status_code == 403


def test_move_and_delete_a_lesson(client, world, h, periods, slot):
    admin = h(world.admin)
    moved = client.patch(f"{BASE}/timetable-slots/{slot['id']}", json={"day_of_week": 2, "period_id": periods[1]["id"], "room": "R-5"}, headers=admin)
    assert moved.status_code == 200
    assert moved.json()["day_of_week"] == 2 and moved.json()["period_no"] == 2 and moved.json()["room"] == "R-5"
    assert client.delete(f"{BASE}/timetable-slots/{slot['id']}", headers=admin).status_code == 204
    assert client.get(f"{BASE}/timetable/sections/{world.section_a.id}", headers=admin).json()["slots"] == []


# ---------------------------------------------------------------- reading
def test_student_reads_own_timetable(client, world, h, slot):
    mine = client.get(f"{BASE}/timetable/me", headers=h(world.su_a1)).json()
    assert [s["id"] for s in mine["slots"]] == [slot["id"]] and len(mine["periods"]) == 3
    assert client.get(f"{BASE}/timetable/me", headers=h(world.su_b1)).json()["slots"] == []


def test_student_cannot_read_another_sections_timetable(client, world, h, slot):
    assert client.get(f"{BASE}/timetable/sections/{world.section_a.id}", headers=h(world.su_a2)).status_code == 200
    assert client.get(f"{BASE}/timetable/sections/{world.section_a.id}", headers=h(world.su_b1)).status_code == 404


def test_parent_reads_only_their_childs_timetable(client, world, h, slot):
    assert client.get(f"{BASE}/timetable/students/{world.st_a1.id}", headers=h(world.pu_a)).status_code == 200
    assert client.get(f"{BASE}/timetable/students/{world.st_a1.id}", headers=h(world.pu_b)).status_code == 404
    assert client.get(f"{BASE}/timetable/sections/{world.section_a.id}", headers=h(world.pu_b)).status_code == 404


def test_teacher_timetable_is_private_to_that_teacher(client, world, h, slot):
    mine = client.get(f"{BASE}/timetable/me", headers=h(world.tu_a)).json()
    assert [s["id"] for s in mine["slots"]] == [slot["id"]]
    assert client.get(f"{BASE}/timetable/teachers/{world.t_a.id}", headers=h(world.tu_a)).status_code == 200
    assert client.get(f"{BASE}/timetable/teachers/{world.t_b.id}", headers=h(world.tu_a)).status_code == 403
    assert client.get(f"{BASE}/timetable/teachers/{world.t_a.id}", headers=h(world.admin)).status_code == 200
    assert client.get(f"{BASE}/timetable/teachers/{world.t_a.id}", headers=h(world.su_a1)).status_code == 403


def test_teacher_with_no_sections_cannot_read_a_section_timetable(client, world, h, slot):
    assert client.get(f"{BASE}/timetable/sections/{world.section_a.id}", headers=h(world.tu_b)).status_code == 404
    assert client.get(f"{BASE}/timetable/sections/{world.section_a.id}", headers=h(world.tu_a)).status_code == 200


def test_data_function_for_pdf_code(db, world, slot):
    from app.modules.timetable.service import get_timetable_data

    data = get_timetable_data(db, world.section_a.id)
    assert data["section"]["name"] == "Class 8-A" and len(data["slots"]) == 1
