"""Homework & assignments: CRUD, validation, teacher scope, student/parent visibility."""
from datetime import timedelta


def body(w, **kw):
    d = {"section_id": str(w.sec_a.id), "subject_id": str(w.math.id), "title": "Chapter 3 exercise",
         "description": "Solve Q1-Q10", "due_date": str(w.today + timedelta(days=3)), "max_marks": 20}
    d.update(kw)
    return d


def test_teacher_creates_assignment_and_audience_is_notified(api, world, db):
    w = world
    r = api.post("/assignments", w.ua, json=body(w))
    assert r.status_code == 201, r.text
    a = r.json()
    assert a["status"] == "published" and a["subject_name"] == "Mathematics" and a["days_left"] == 3
    assert a["is_overdue"] is False
    # students of 8-A and the parent of a1 get a notification
    assert api.get("/notifications/unread-count", w.user_a1).json()["count"] >= 1
    assert api.get("/notifications/unread-count", w.up1).json()["count"] >= 1


def test_draft_is_hidden_from_students_and_parents(api, world):
    w = world
    a = api.post("/assignments", w.ua, json=body(w, status="draft")).json()
    assert api.get("/assignments", w.user_a1).json()["total"] == 0
    assert api.get("/assignments", w.up1).json()["total"] == 0
    assert api.get(f"/assignments/{a['id']}", w.user_a1).status_code == 404
    assert api.get("/assignments", w.ua).json()["total"] == 1


def test_validation(api, world):
    w = world
    r = api.post("/assignments", w.ua, json=body(w, title="ab"))
    assert r.status_code == 422
    r = api.post("/assignments", w.ua, json=body(w, due_date=str(w.today - timedelta(days=1))))
    assert r.status_code == 422
    r = api.post("/assignments", w.ua, json=body(w, max_marks=-5))
    assert r.status_code == 422


def test_teacher_cannot_assign_outside_own_classes(api, world):
    w = world
    # teacher_b teaches 8-B only; teacher_c nothing; teacher_a does not teach Science
    assert api.post("/assignments", w.ub, json=body(w)).status_code == 403
    assert api.post("/assignments", w.uc, json=body(w)).status_code == 403
    assert api.post("/assignments", w.ua, json=body(w, subject_id=str(w.science.id))).status_code == 403


def test_student_and_parent_cannot_create(api, world):
    w = world
    assert api.post("/assignments", w.user_a1, json=body(w)).status_code == 403
    assert api.post("/assignments", w.up1, json=body(w)).status_code == 403
    assert api.post("/assignments", None, json=body(w)).status_code == 401


def test_visibility_scoping(api, world):
    w = world
    api.post("/assignments", w.ua, json=body(w))                                   # 8-A
    api.post("/assignments", w.ub, json=body(w, section_id=str(w.sec_b.id)))       # 8-B
    assert api.get("/assignments", w.user_a1).json()["total"] == 1
    assert api.get("/assignments", w.user_b2).json()["total"] == 1
    assert api.get("/assignments", w.up1).json()["total"] == 2        # children in 8-A and 8-B
    assert api.get("/assignments", w.up2).json()["total"] == 1        # child in 8-B only
    assert api.get("/assignments", w.ua).json()["total"] == 1         # teacher: own only
    assert api.get("/assignments", w.admin).json()["total"] == 2
    assert api.get("/assignments", w.user_c1).json()["total"] == 0    # other class sees nothing


def test_only_owner_can_edit_or_delete(api, world):
    w = world
    a = api.post("/assignments", w.ua, json=body(w)).json()
    assert api.patch(f"/assignments/{a['id']}", w.ub, json={"title": "Hacked title"}).status_code in (403, 404)
    assert api.delete(f"/assignments/{a['id']}", w.ub).status_code in (403, 404)
    r = api.patch(f"/assignments/{a['id']}", w.ua, json={"title": "Updated title", "max_marks": 25})
    assert r.status_code == 200 and r.json()["title"] == "Updated title"
    assert api.patch(f"/assignments/{a['id']}", w.user_a1, json={"title": "Nope nope"}).status_code == 403
    assert api.delete(f"/assignments/{a['id']}", w.ua).status_code == 204
    assert api.get(f"/assignments/{a['id']}", w.ua).status_code == 404


def test_update_validation_and_close(api, world):
    w = world
    a = api.post("/assignments", w.ua, json=body(w)).json()
    r = api.patch(f"/assignments/{a['id']}", w.ua, json={"due_date": str(w.today - timedelta(days=2))})
    assert r.status_code == 422
    r = api.patch(f"/assignments/{a['id']}", w.ua, json={"status": "closed"})
    assert r.status_code == 200 and r.json()["status"] == "closed"


def test_filters_and_pagination(api, world):
    w = world
    for i in range(5):
        api.post("/assignments", w.ua, json=body(w, title=f"Task number {i}"))
    r = api.get("/assignments?page=1&page_size=2", w.ua).json()
    assert r["total"] == 5 and len(r["items"]) == 2
    assert api.get(f"/assignments?subject_id={w.english.id}", w.ua).json()["total"] == 0
    assert api.get("/assignments?page_size=1000", w.ua).status_code == 422


def test_attachment_upload_and_download(api, world):
    w = world
    a = api.post("/assignments", w.ua, json=body(w)).json()
    files = {"file": ("worksheet.pdf", b"%PDF-1.4 test", "application/pdf")}
    r = api.post(f"/assignments/{a['id']}/attachment", w.ua, files=files)
    assert r.status_code in (200, 201), r.text
    r = api.get(f"/assignments/{a['id']}/attachment", w.user_a1)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    assert api.get(f"/assignments/{a['id']}/attachment", w.user_b2).status_code in (403, 404)
    bad = {"file": ("evil.exe", b"MZ....", "application/x-msdownload")}
    assert api.post(f"/assignments/{a['id']}/attachment", w.ua, files=bad).status_code in (400, 415, 422)
