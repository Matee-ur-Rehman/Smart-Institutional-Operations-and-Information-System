"""Module: Exams, Marks & Results."""
import pytest

from tests.conftest import assert_validation_error
from tests.ops.helpers import day

EXAMS = "/api/v1/exams"
GRADES = [
    {"grade": "A+", "min_percentage": 90, "max_percentage": 100, "remark": "Outstanding", "is_pass": True},
    {"grade": "A", "min_percentage": 80, "max_percentage": 89.99, "remark": "Excellent", "is_pass": True},
    {"grade": "B", "min_percentage": 70, "max_percentage": 79.99, "remark": "Very good", "is_pass": True},
    {"grade": "C", "min_percentage": 60, "max_percentage": 69.99, "remark": "Good", "is_pass": True},
    {"grade": "D", "min_percentage": 50, "max_percentage": 59.99, "remark": "Satisfactory", "is_pass": True},
    {"grade": "F", "min_percentage": 0, "max_percentage": 49.99, "remark": "Fail", "is_pass": False},
]


def schedule_body(w, subject, start="09:00", end="10:00", total=100, passing=40, section=None, offset=1):
    return {
        "section_id": str((section or w.section_a).id),
        "subject_id": str(subject.id),
        "exam_date": day(offset),
        "start_time": start,
        "end_time": end,
        "total_marks": total,
        "passing_marks": passing,
    }


@pytest.fixture
def setup(client, world, h):
    """Grade scale + a 'scheduled' exam with English (100) and Maths (50) papers for section A."""
    admin = h(world.admin)
    assert client.put("/api/v1/grade-scales", json={"bands": GRADES}, headers=admin).status_code == 200
    r = client.post(
        EXAMS,
        json={"name": "Mid-term 2026", "exam_type": "midterm", "start_date": day(0), "end_date": day(5), "status": "scheduled"},
        headers=admin,
    )
    assert r.status_code == 201, r.text
    exam = r.json()
    eng = client.post(f"{EXAMS}/{exam['id']}/schedules", json=schedule_body(world, world.english), headers=admin)
    mat = client.post(
        f"{EXAMS}/{exam['id']}/schedules",
        json=schedule_body(world, world.maths, start="10:30", end="11:30", total=50, passing=20),
        headers=admin,
    )
    assert eng.status_code == 201 and mat.status_code == 201, (eng.text, mat.text)
    return {"exam": exam, "english": eng.json(), "maths": mat.json()}


def put_marks(client, headers, schedule_id, entries):
    return client.put(f"/api/v1/exam-schedules/{schedule_id}/marks", json={"entries": entries}, headers=headers)


def enter_all(client, world, h, setup):
    """A1: English 80/100, Maths 40/50.  A2: English 30/100, Maths absent."""
    r1 = put_marks(client, h(world.tu_a), setup["english"]["id"], [
        {"student_id": str(world.st_a1.id), "marks_obtained": 80},
        {"student_id": str(world.st_a2.id), "marks_obtained": 30},
    ])
    r2 = put_marks(client, h(world.tu_a), setup["maths"]["id"], [
        {"student_id": str(world.st_a1.id), "marks_obtained": 40},
        {"student_id": str(world.st_a2.id), "is_absent": True},
    ])
    assert r1.status_code == 200 and r2.status_code == 200, (r1.text, r2.text)


# ---------------------------------------------------------------- exams and papers
def test_only_admin_creates_exams(client, world, h):
    body = {"name": "Quiz", "exam_type": "monthly", "start_date": day(0), "end_date": day(1)}
    assert client.post(EXAMS, json=body, headers=h(world.tu_a)).status_code == 403
    assert client.post(EXAMS, json=body, headers=h(world.pu_a)).status_code == 403
    assert client.post(EXAMS, json=body, headers=h(world.admin)).status_code == 201


def test_exam_dates_are_validated(client, world, h):
    body = {"name": "Quiz", "exam_type": "monthly", "start_date": day(3), "end_date": day(1)}
    assert_validation_error(client.post(EXAMS, json=body, headers=h(world.admin)))


def test_draft_exams_are_hidden_from_everyone_but_admin(client, world, h):
    draft = client.post(
        EXAMS, json={"name": "Secret exam", "exam_type": "final", "start_date": day(0), "end_date": day(2)}, headers=h(world.admin)
    ).json()
    assert draft["status"] == "draft"
    assert client.get(f"{EXAMS}/{draft['id']}", headers=h(world.admin)).status_code == 200
    for who in (world.tu_a, world.su_a1, world.pu_a):
        assert client.get(f"{EXAMS}/{draft['id']}", headers=h(who)).status_code == 404
        assert client.get(EXAMS, headers=h(who)).json()["items"] == []


def test_paper_must_fall_inside_exam_dates(client, world, h, setup):
    body = schedule_body(world, world.science, offset=30)
    r = client.post(f"{EXAMS}/{setup['exam']['id']}/schedules", json=body, headers=h(world.admin))
    assert r.status_code == 400


def test_duplicate_and_overlapping_papers_conflict(client, world, h, setup):
    admin = h(world.admin)
    url = f"{EXAMS}/{setup['exam']['id']}/schedules"
    assert client.post(url, json=schedule_body(world, world.english), headers=admin).status_code == 409
    clash = schedule_body(world, world.science, start="09:30", end="10:30")
    assert client.post(url, json=clash, headers=admin).status_code == 409


def test_passing_marks_cannot_exceed_total(client, world, h, setup):
    body = schedule_body(world, world.science, start="12:00", end="13:00", total=50, passing=60)
    r = client.post(f"{EXAMS}/{setup['exam']['id']}/schedules", json=body, headers=h(world.admin))
    assert_validation_error(r)


def test_schedule_visibility_follows_section(client, world, h, setup):
    url = f"{EXAMS}/{setup['exam']['id']}/schedules"
    assert len(client.get(url, headers=h(world.su_a1)).json()) == 2
    assert len(client.get(url, headers=h(world.pu_a)).json()) == 2
    assert client.get(url, headers=h(world.su_b1)).json() == []
    assert client.get(url, headers=h(world.pu_b)).json() == []
    assert len(client.get(url, headers=h(world.admin)).json()) == 2


def test_delete_only_draft_exams(client, world, h, setup):
    assert client.delete(f"{EXAMS}/{setup['exam']['id']}", headers=h(world.admin)).status_code == 409
    draft = client.post(
        EXAMS, json={"name": "Scrap exam", "exam_type": "other", "start_date": day(0), "end_date": day(1)}, headers=h(world.admin)
    ).json()
    client.post(f"{EXAMS}/{draft['id']}/schedules", json=schedule_body(world, world.english), headers=h(world.admin))
    assert client.delete(f"{EXAMS}/{draft['id']}", headers=h(world.admin)).status_code == 204


# ---------------------------------------------------------------- entering marks
def test_assigned_teacher_enters_marks(client, world, h, setup):
    r = put_marks(client, h(world.tu_a), setup["english"]["id"], [
        {"student_id": str(world.st_a1.id), "marks_obtained": 80},
        {"student_id": str(world.st_a2.id), "marks_obtained": 30.5},
    ])
    assert r.status_code == 200 and r.json() == {"saved": 2}
    sheet = client.get(f"/api/v1/exam-schedules/{setup['english']['id']}/marks", headers=h(world.tu_a)).json()
    by_roll = {row["roll_no"]: row for row in sheet["rows"]}
    assert by_roll["A-01"]["marks_obtained"] == 80 and by_roll["A-02"]["marks_obtained"] == 30.5


def test_marks_can_be_corrected_before_publishing(client, world, h, setup):
    sid = setup["english"]["id"]
    entry = {"student_id": str(world.st_a1.id), "marks_obtained": 50}
    put_marks(client, h(world.tu_a), sid, [entry])
    put_marks(client, h(world.tu_a), sid, [{**entry, "marks_obtained": 55}])
    rows = client.get(f"/api/v1/exam-schedules/{sid}/marks", headers=h(world.admin)).json()["rows"]
    assert [r["marks_obtained"] for r in rows if r["roll_no"] == "A-01"] == [55]


def test_teacher_who_does_not_teach_the_subject_is_refused(client, world, h, setup):
    science = client.post(
        f"{EXAMS}/{setup['exam']['id']}/schedules",
        json=schedule_body(world, world.science, start="12:00", end="13:00"),
        headers=h(world.admin),
    ).json()
    entry = [{"student_id": str(world.st_a1.id), "marks_obtained": 10}]
    assert put_marks(client, h(world.tu_a), science["id"], entry).status_code == 403  # teaches English/Maths only
    assert put_marks(client, h(world.tu_b), setup["english"]["id"], entry).status_code == 403
    assert client.get(f"/api/v1/exam-schedules/{setup['english']['id']}/marks", headers=h(world.tu_b)).status_code == 403


@pytest.mark.parametrize("who", ["su_a1", "pu_a"])
def test_students_and_parents_cannot_touch_marks(client, world, h, setup, who):
    sid = setup["english"]["id"]
    assert put_marks(client, h(getattr(world, who)), sid, [{"student_id": str(world.st_a1.id), "marks_obtained": 99}]).status_code == 403
    assert client.get(f"/api/v1/exam-schedules/{sid}/marks", headers=h(getattr(world, who))).status_code == 403


def test_marks_above_total_are_rejected(client, world, h, setup):
    r = put_marks(client, h(world.tu_a), setup["maths"]["id"], [{"student_id": str(world.st_a1.id), "marks_obtained": 51}])
    assert r.status_code == 400


def test_negative_marks_are_rejected(client, world, h, setup):
    r = put_marks(client, h(world.tu_a), setup["maths"]["id"], [{"student_id": str(world.st_a1.id), "marks_obtained": -1}])
    assert_validation_error(r)


def test_student_from_another_section_is_rejected(client, world, h, setup):
    r = put_marks(client, h(world.tu_a), setup["english"]["id"], [{"student_id": str(world.st_b1.id), "marks_obtained": 70}])
    assert r.status_code == 400


def test_absent_student_cannot_also_have_marks(client, world, h, setup):
    entry = {"student_id": str(world.st_a1.id), "marks_obtained": 10, "is_absent": True}
    assert_validation_error(put_marks(client, h(world.tu_a), setup["english"]["id"], [entry]))


def test_present_student_needs_marks(client, world, h, setup):
    assert_validation_error(put_marks(client, h(world.tu_a), setup["english"]["id"], [{"student_id": str(world.st_a1.id)}]))


def test_duplicate_student_in_one_request_is_rejected(client, world, h, setup):
    entry = {"student_id": str(world.st_a1.id), "marks_obtained": 10}
    assert put_marks(client, h(world.tu_a), setup["english"]["id"], [entry, entry]).status_code == 400


def test_nothing_is_saved_when_one_entry_is_invalid(client, world, h, setup):
    sid = setup["english"]["id"]
    put_marks(client, h(world.tu_a), sid, [
        {"student_id": str(world.st_a1.id), "marks_obtained": 60},
        {"student_id": str(world.st_a2.id), "marks_obtained": 500},
    ])
    rows = client.get(f"/api/v1/exam-schedules/{sid}/marks", headers=h(world.admin)).json()["rows"]
    assert all(r["marks_obtained"] is None for r in rows)


# ---------------------------------------------------------------- results
def test_results_are_hidden_until_published(client, world, h, setup):
    enter_all(client, world, h, setup)
    url = f"/api/v1/results/students/{world.st_a1.id}"
    assert client.get(url, params={"exam_id": setup["exam"]["id"]}, headers=h(world.pu_a)).status_code == 404
    assert client.get(url, headers=h(world.pu_a)).json()["results"] == []
    assert client.get(url, headers=h(world.su_a1)).json()["results"] == []
    admin_view = client.get(url, params={"exam_id": setup["exam"]["id"]}, headers=h(world.admin))
    assert admin_view.status_code == 200


def test_publish_computes_grades_and_positions(client, world, h, notes, setup):
    enter_all(client, world, h, setup)
    r = client.post(f"{EXAMS}/{setup['exam']['id']}/publish-results", headers=h(world.admin))
    assert r.status_code == 200 and r.json()["status"] == "results_published"

    got = client.get(f"/api/v1/results/students/{world.st_a1.id}", headers=h(world.pu_a))
    assert got.status_code == 200
    entry = got.json()["results"][0]
    assert entry["exam"]["name"] == "Mid-term 2026"
    a1 = entry["result"]
    assert a1["total_obtained"] == 120 and a1["total_marks"] == 150 and a1["percentage"] == 80
    assert a1["grade"] == "A" and a1["complete"] is True and a1["passed"] is True and a1["position"] == 1
    subjects = {s["subject_name"]: s for s in a1["subjects"]}
    assert subjects["English"]["grade"] == "A" and subjects["Mathematics"]["percentage"] == 80

    a2 = client.get(f"/api/v1/results/students/{world.st_a2.id}", headers=h(world.su_a2)).json()["results"][0]["result"]
    assert a2["total_obtained"] == 30 and a2["percentage"] == 20 and a2["grade"] == "F"
    assert a2["passed"] is False and a2["position"] == 2
    maths = {s["subject_name"]: s for s in a2["subjects"]}["Mathematics"]
    assert maths["status"] == "absent" and maths["grade"] == "ABS" and maths["marks_obtained"] is None

    # section A is told, section B is not
    for user in (world.su_a1, world.su_a2, world.pu_a):
        assert len(notes(user, "marks")) == 1
    assert notes(world.su_b1, "marks") == [] and notes(world.pu_b, "marks") == []


def test_publish_twice_and_empty_exam_are_refused(client, world, h, setup):
    assert client.post(f"{EXAMS}/{setup['exam']['id']}/publish-results", headers=h(world.admin)).status_code == 200
    assert client.post(f"{EXAMS}/{setup['exam']['id']}/publish-results", headers=h(world.admin)).status_code == 409
    empty = client.post(
        EXAMS, json={"name": "No papers", "exam_type": "other", "start_date": day(0), "end_date": day(1), "status": "scheduled"},
        headers=h(world.admin),
    ).json()
    assert client.post(f"{EXAMS}/{empty['id']}/publish-results", headers=h(world.admin)).status_code == 400


@pytest.mark.parametrize("who", ["tu_a", "su_a1", "pu_a"])
def test_only_admin_publishes(client, world, h, setup, who):
    assert client.post(f"{EXAMS}/{setup['exam']['id']}/publish-results", headers=h(getattr(world, who))).status_code == 403


def test_marks_and_status_are_locked_after_publishing(client, world, h, setup):
    enter_all(client, world, h, setup)
    client.post(f"{EXAMS}/{setup['exam']['id']}/publish-results", headers=h(world.admin))
    entry = [{"student_id": str(world.st_a1.id), "marks_obtained": 99}]
    assert put_marks(client, h(world.tu_a), setup["english"]["id"], entry).status_code == 409
    assert put_marks(client, h(world.admin), setup["english"]["id"], entry).status_code == 409
    assert client.patch(f"{EXAMS}/{setup['exam']['id']}", json={"status": "draft"}, headers=h(world.admin)).status_code == 409
    assert client.post(f"{EXAMS}/{setup['exam']['id']}/schedules", json=schedule_body(world, world.science, start="14:00", end="15:00"), headers=h(world.admin)).status_code == 409


def test_nobody_reads_another_familys_results(client, world, h, setup):
    enter_all(client, world, h, setup)
    client.post(f"{EXAMS}/{setup['exam']['id']}/publish-results", headers=h(world.admin))
    url = f"/api/v1/results/students/{world.st_a1.id}"
    assert client.get(url, headers=h(world.pu_b)).status_code == 404   # parent of another child
    assert client.get(url, headers=h(world.su_a2)).status_code == 404  # classmate
    assert client.get(url, headers=h(world.su_b1)).status_code == 404  # other section
    assert client.get(url, headers=h(world.tu_b)).status_code == 404   # teacher with no sections
    assert client.get(url, headers=h(world.tu_a)).status_code == 200   # teaches the section
    assert client.get(url, headers=h(world.su_a1)).status_code == 200  # the student themselves


def test_section_results(client, world, h, setup):
    enter_all(client, world, h, setup)
    url = f"/api/v1/results/sections/{world.section_a.id}"
    params = {"exam_id": setup["exam"]["id"]}
    rows = client.get(url, params=params, headers=h(world.admin)).json()
    assert [r["roll_no"] for r in rows] == ["A-01", "A-02"]
    assert client.get(url, params=params, headers=h(world.tu_a)).status_code == 200
    assert client.get(url, params=params, headers=h(world.tu_b)).status_code == 404
    assert client.get(url, params=params, headers=h(world.pu_a)).status_code == 403
    assert client.get(url, headers=h(world.admin)).status_code == 422  # exam_id is required


def test_incomplete_results_have_no_pass_verdict(client, world, h, setup):
    put_marks(client, h(world.tu_a), setup["english"]["id"], [{"student_id": str(world.st_a1.id), "marks_obtained": 90}])
    rows = client.get(
        f"/api/v1/results/sections/{world.section_a.id}", params={"exam_id": setup["exam"]["id"]}, headers=h(world.admin)
    ).json()
    a1 = next(r for r in rows if r["roll_no"] == "A-01")
    assert a1["complete"] is False and a1["passed"] is None
    pending = [s for s in a1["subjects"] if s["status"] == "pending"]
    assert len(pending) == 1


# ---------------------------------------------------------------- grade scale
def test_grade_scale_readable_by_everyone_writable_by_admin(client, world, h, setup):
    for who in (world.tu_a, world.su_a1, world.pu_a):
        assert len(client.get("/api/v1/grade-scales", headers=h(who)).json()) == len(GRADES)
        assert client.put("/api/v1/grade-scales", json={"bands": GRADES}, headers=h(who)).status_code == 403


def test_overlapping_grade_bands_are_rejected(client, world, h):
    bands = [
        {"grade": "A", "min_percentage": 50, "max_percentage": 100},
        {"grade": "B", "min_percentage": 0, "max_percentage": 60},
    ]
    assert client.put("/api/v1/grade-scales", json={"bands": bands}, headers=h(world.admin)).status_code == 422


def test_duplicate_grade_letters_are_rejected(client, world, h):
    bands = [
        {"grade": "A", "min_percentage": 50, "max_percentage": 100},
        {"grade": "a", "min_percentage": 0, "max_percentage": 49},
    ]
    assert client.put("/api/v1/grade-scales", json={"bands": bands}, headers=h(world.admin)).status_code == 422
