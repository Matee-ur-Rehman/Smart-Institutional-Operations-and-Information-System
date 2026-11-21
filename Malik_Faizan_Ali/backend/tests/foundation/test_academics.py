"""Academic years, classes, sections, subjects, teacher assignments."""
from datetime import timedelta


def test_academic_years(api, world):
    w = world
    assert [y["name"] for y in api.get("/academic-years", w.user_a1).json()] == ["2026-2027"]
    body = {"name": "2027-2028", "start_date": str(w.today + timedelta(days=300)), "end_date": str(w.today + timedelta(days=650))}
    r = api.post("/academic-years", w.admin, json=body)
    assert r.status_code == 201 and r.json()["is_current"] is False
    assert api.post("/academic-years", w.admin, json=body).status_code == 409
    assert api.post("/academic-years", w.admin, json=dict(body, name="2030-2031", end_date=body["start_date"])).status_code == 422
    assert api.post("/academic-years", w.ua, json=body).status_code == 403
    yid = r.json()["id"]
    assert api.patch(f"/academic-years/{yid}", w.admin, json={"end_date": str(w.today)}).status_code == 422
    assert api.post(f"/academic-years/{yid}/set-current", w.admin).json()["is_current"] is True
    years = api.get("/academic-years", w.admin).json()
    assert [y["name"] for y in years if y["is_current"]] == ["2027-2028"]                  # exactly one current year
    assert api.post(f"/academic-years/{yid}/set-current", w.ua).status_code == 403


def test_classes(api, world):
    w = world
    assert [c["name"] for c in api.get("/classes", w.user_a1).json()] == ["Class 8", "Class 9"]
    assert api.get("/classes", w.user_a1).json()[0]["section_count"] == 2
    assert api.post("/classes", w.admin, json={"name": "Class 10", "grade_level": 10}).status_code == 201
    assert api.post("/classes", w.admin, json={"name": "class 10", "grade_level": 10}).status_code == 409
    assert api.post("/classes", w.admin, json={"name": "Class 99", "grade_level": 99}).status_code == 422
    assert api.post("/classes", w.ua, json={"name": "Nursery", "grade_level": 0}).status_code == 403
    assert api.patch(f"/classes/{w.class8.id}", w.admin, json={"is_active": False}).status_code == 409        # has active students
    assert api.patch(f"/classes/{w.class9.id}", w.admin, json={"name": "Class 8"}).status_code == 409
    c10 = api.get("/classes", w.admin).json()[-1]
    assert api.patch(f"/classes/{c10['id']}", w.admin, json={"is_active": False}).status_code == 200
    assert "Class 10" not in [c["name"] for c in api.get("/classes", w.admin).json()]
    assert "Class 10" in [c["name"] for c in api.get("/classes?include_inactive=true", w.admin).json()]


def test_sections(api, world):
    w = world
    secs = api.get(f"/sections?class_id={w.class8.id}", w.ua).json()
    assert [s["label"] for s in secs] == ["Class 8-A", "Class 8-B"] and secs[0]["student_count"] == 3
    r = api.post("/sections", w.admin, json={"class_id": str(w.class9.id), "name": "b", "class_teacher_id": str(w.teacher_a.id)})
    assert r.status_code == 201 and r.json()["name"] == "B" and r.json()["class_teacher_name"] == "Teacher A"
    assert api.post("/sections", w.admin, json={"class_id": str(w.class9.id), "name": "B"}).status_code == 409
    assert api.post("/sections", w.admin, json={"class_id": "00000000-0000-0000-0000-000000000000", "name": "C"}).status_code == 422
    assert api.post("/sections", w.admin, json={"class_id": str(w.class9.id), "name": "C", "class_teacher_id": "00000000-0000-0000-0000-000000000000"}).status_code == 422
    assert api.post("/sections", w.ua, json={"class_id": str(w.class9.id), "name": "D"}).status_code == 403
    assert api.patch(f"/sections/{w.sec_a.id}", w.admin, json={"is_active": False}).status_code == 409        # students inside
    assert api.patch(f"/sections/{w.sec_a.id}", w.admin, json={"class_teacher_id": str(w.teacher_b.id)}).json()["class_teacher_name"] == "Teacher B"
    assert api.patch(f"/sections/{w.sec_a.id}", w.admin, json={"name": "B"}).status_code == 409
    assert api.get(f"/teachers/{w.teacher_b.id}", w.admin).json()["class_teacher_of"][0]["section_label"] == "Class 8-A"
    new = r.json()["id"]
    assert api.patch(f"/sections/{new}", w.admin, json={"is_active": False}).status_code == 200                # empty -> ok


def test_subjects(api, world):
    w = world
    assert len(api.get("/subjects", w.user_a1).json()) == 3
    r = api.post("/subjects", w.admin, json={"name": "Computer Science", "code": "cs"})
    assert r.status_code == 201 and r.json()["code"] == "CS"
    assert api.post("/subjects", w.admin, json={"name": "Another", "code": "CS"}).status_code == 409
    assert api.post("/subjects", w.admin, json={"name": "X", "code": "BAD CODE"}).status_code == 422
    assert api.post("/subjects", w.ua, json={"name": "Nope Nope", "code": "NP"}).status_code == 403
    sid = r.json()["id"]
    assert api.patch(f"/subjects/{sid}", w.admin, json={"code": "COMP"}).json()["code"] == "COMP"
    assert api.patch(f"/subjects/{sid}", w.admin, json={"is_active": False}).status_code == 200
    assert len(api.get("/subjects", w.admin).json()) == 3


def test_teacher_assignments(api, world):
    w = world
    assert len(api.get("/teacher-assignments", w.ua).json()) == 3
    assert len(api.get(f"/teacher-assignments?teacher_id={w.teacher_a.id}", w.admin).json()) == 2
    body = {"teacher_id": str(w.teacher_c.id), "section_id": str(w.sec_b.id), "subject_id": str(w.english.id)}
    r = api.post("/teacher-assignments", w.admin, json=body)
    assert r.status_code == 201 and r.json()["teacher_name"] == "Teacher C"
    assert api.post("/teacher-assignments", w.admin, json=dict(body, teacher_id=str(w.teacher_a.id))).status_code == 409   # one teacher per subject+section
    assert api.post("/teacher-assignments", w.admin, json=dict(body, teacher_id="00000000-0000-0000-0000-000000000000")).status_code == 422
    for u in (w.ua, w.user_a1, w.up1):
        assert api.post("/teacher-assignments", u, json=body).status_code == 403
    assert api.get("/teacher-assignments", w.user_a1).status_code == 403
    aid = r.json()["id"]
    # the new assignment immediately gives the teacher access to that section
    assert api.get(f"/students?section_id={w.sec_b.id}", w.uc).json()["total"] == 2
    assert api.patch(f"/teacher-assignments/{aid}", w.admin, json={"teacher_id": str(w.teacher_b.id)}).json()["teacher_name"] == "Teacher B"
    assert api.delete(f"/teacher-assignments/{aid}", w.admin).status_code == 204
    assert api.delete(f"/teacher-assignments/{aid}", w.admin).status_code == 404
    assert api.get(f"/students?section_id={w.sec_b.id}", w.uc).json()["total"] == 0
