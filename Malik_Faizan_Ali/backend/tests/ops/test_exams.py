"""Exams, marks entry, grades, results and publishing."""
from datetime import timedelta

from tests.conftest import entries


def test_exam_crud_validation_and_roles(api, world):
    w = world
    ok = {"name": "Monthly Test Oct", "exam_type": "monthly", "start_date": str(w.today), "end_date": str(w.today + timedelta(days=2))}
    r = api.post("/exams", w.admin, json=ok)
    assert r.status_code == 201 and r.json()["status"] == "draft"
    bad = dict(ok, end_date=str(w.today - timedelta(days=1)))
    assert api.post("/exams", w.admin, json=bad).status_code == 422
    assert api.post("/exams", w.admin, json=dict(ok, exam_type="surprise")).status_code == 422
    for u in (w.ua, w.user_a1, w.up1):
        assert api.post("/exams", u, json=ok).status_code == 403
    assert api.post("/exams", None, json=ok).status_code == 401
    eid = r.json()["id"]
    assert api.patch(f"/exams/{eid}", w.admin, json={"status": "scheduled"}).json()["status"] == "scheduled"
    assert api.delete(f"/exams/{eid}", w.admin).status_code == 400          # only drafts can be deleted


def test_draft_exam_hidden_from_students(api, world):
    w = world
    api.post("/exams", w.admin, json={"name": "Hidden Draft", "exam_type": "final", "start_date": str(w.today),
                                      "end_date": str(w.today)})
    assert api.get("/exams", w.admin).json()["total"] == 1
    assert api.get("/exams", w.user_a1).json()["total"] == 0


def test_schedule_rules(api, world, make_exam):
    w = world
    exam, papers = make_exam()
    base = {"section_id": str(w.sec_a.id), "subject_id": str(w.math.id), "exam_date": str(w.today + timedelta(days=2)),
            "start_time": "09:00", "end_time": "11:00", "total_marks": 100, "passing_marks": 33}
    assert api.post(f"/exams/{exam['id']}/schedules", w.admin, json=base).status_code == 409   # duplicate paper
    clash = dict(base, subject_id=str(w.science.id), exam_date=str(w.today + timedelta(days=1)), start_time="10:00", end_time="12:00")
    assert api.post(f"/exams/{exam['id']}/schedules", w.admin, json=clash).status_code == 409   # time clash in section
    assert api.post(f"/exams/{exam['id']}/schedules", w.admin, json=dict(base, passing_marks=150, total_marks=100)).status_code == 422
    assert api.post(f"/exams/{exam['id']}/schedules", w.admin, json=dict(base, end_time="08:00")).status_code == 422
    assert api.post(f"/exams/{exam['id']}/schedules", w.ua, json=base).status_code == 403


def test_marks_entry_validation_and_teacher_scope(api, world, make_exam):
    w = world
    _, papers = make_exam()
    sid = papers["math"]["id"]
    ok = api.put(f"/exam-schedules/{sid}/marks", w.ua, json=entries((w.a1, 85), (w.a2, 30), (w.a3, None, True)))
    assert ok.status_code == 200, ok.text
    rows = {r["roll_no"]: r for r in ok.json()["rows"]}
    assert rows["A1"]["grade"] == "A" and rows["A1"]["passed"] is True
    assert rows["A2"]["grade"] == "F" and rows["A2"]["passed"] is False
    assert rows["A3"]["is_absent"] is True
    # marks above total
    assert api.put(f"/exam-schedules/{sid}/marks", w.ua, json=entries((w.a1, 101))).status_code == 422
    assert api.put(f"/exam-schedules/{sid}/marks", w.ua, json=entries((w.a1, -1))).status_code == 422
    # student from another section
    assert api.put(f"/exam-schedules/{sid}/marks", w.ua, json=entries((w.b1, 50))).status_code == 422
    # other teacher / students / parents cannot enter
    assert api.put(f"/exam-schedules/{sid}/marks", w.ub, json=entries((w.a1, 50))).status_code in (403, 404)
    assert api.put(f"/exam-schedules/{sid}/marks", w.user_a1, json=entries((w.a1, 99))).status_code == 403
    # English paper belongs to teacher_a too, but math teacher_b is wrong person
    assert api.get(f"/exam-schedules/{sid}/marks", w.ub).status_code in (403, 404)
    assert api.get(f"/exam-schedules/{sid}/marks", w.ua).status_code == 200


def test_marks_blocked_for_draft_exam(api, world, make_exam):
    w = world
    _, papers = make_exam(status="draft")
    r = api.put(f"/exam-schedules/{papers['math']['id']}/marks", w.ua, json=entries((w.a1, 50)))
    assert r.status_code == 400


def test_publish_flow_and_visibility(api, world, make_exam):
    w = world
    exam, papers = make_exam()
    eid = exam["id"]
    assert api.post(f"/exams/{eid}/publish-results", w.admin).status_code == 400          # no marks yet
    api.put(f"/exam-schedules/{papers['math']['id']}/marks", w.ua, json=entries((w.a1, 90), (w.a2, 20), (w.a3, 70)))
    api.put(f"/exam-schedules/{papers['eng']['id']}/marks", w.ua, json=entries((w.a1, 80), (w.a2, 35), (w.a3, 75)))
    # results are not visible to student/parent before publishing
    assert api.get(f"/results/students/{w.a1.id}", w.user_a1).json()["results"] == []
    assert api.post(f"/exams/{eid}/publish-results", w.ua).status_code == 403
    r = api.post(f"/exams/{eid}/publish-results", w.admin)
    assert r.status_code == 200 and r.json()["status"] == "results_published"
    assert api.post(f"/exams/{eid}/publish-results", w.admin).status_code == 409
    # published => student sees own, parent sees child, nobody sees others
    mine = api.get(f"/results/students/{w.a1.id}?exam_id={eid}", w.user_a1)
    assert mine.status_code == 200 and len(mine.json()["results"]) == 1
    assert api.get(f"/results/students/{w.a1.id}?exam_id={eid}", w.up1).status_code == 200
    assert api.get(f"/results/students/{w.a1.id}", w.user_a2).status_code == 404
    assert api.get(f"/results/students/{w.a1.id}", w.up2).status_code == 404
    # notification went out
    assert api.get("/notifications/unread-count", w.user_a1).json()["count"] >= 1
    # marks are locked after publishing
    assert api.put(f"/exam-schedules/{papers['math']['id']}/marks", w.ua, json=entries((w.a1, 10))).status_code == 409
    # section result summary for staff
    sec = api.get(f"/results/sections/{w.sec_a.id}?exam_id={eid}", w.admin).json()
    assert sec["summary"]["students"] == 3 and sec["summary"]["failed"] >= 1
    assert api.get(f"/results/sections/{w.sec_a.id}?exam_id={eid}", w.user_a1).status_code == 403


def test_grade_scale_validation(api, world):
    w = world
    assert api.get("/grade-scales", w.user_a1).status_code == 200
    good = {"bands": [{"grade": "P", "min_percentage": 40, "max_percentage": 100, "is_pass": True},
                      {"grade": "F", "min_percentage": 0, "max_percentage": 39.99, "is_pass": False}]}
    assert api.put("/grade-scales", w.admin, json=good).status_code == 200
    gap = {"bands": [{"grade": "P", "min_percentage": 60, "max_percentage": 100}, {"grade": "F", "min_percentage": 0, "max_percentage": 40}]}
    assert api.put("/grade-scales", w.admin, json=gap).status_code == 422
    overlap = {"bands": [{"grade": "P", "min_percentage": 30, "max_percentage": 100}, {"grade": "F", "min_percentage": 0, "max_percentage": 40}]}
    assert api.put("/grade-scales", w.admin, json=overlap).status_code == 422
    assert api.put("/grade-scales", w.ua, json=good).status_code == 403
