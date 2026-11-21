"""Teachers, students, parents and parent-child links."""
from datetime import date, timedelta

from tests.foundation.test_auth import login


def student_body(w, **kw):
    d = {"full_name": "Hamza Tariq", "roll_no": "8A-101", "section_id": str(w.sec_a.id), "gender": "male",
         "date_of_birth": "2012-03-04", "address": "House 5, Hassan Abdal"}
    d.update(kw)
    return d


# ------------------------------------------------------------------ teachers
def test_teacher_create_and_login(api, world):
    w = world
    r = api.post("/teachers", w.admin, json={"full_name": "Sana Malik", "employee_no": "EMP-77", "qualification": "MSc Physics",
                                             "phone": "0300-7654321", "email": "sana@example.com"})
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["login_id"] == "emp-77" and t["temporary_password"] and t["assignments"] == []
    assert login(api, "emp-77", t["temporary_password"], "mobile").status_code == 200
    assert api.post("/teachers", w.admin, json={"full_name": "Dup Emp", "employee_no": "emp-77"}).status_code == 409
    assert api.post("/teachers", w.admin, json={"full_name": "Dup Login", "employee_no": "EMP-78", "login_id": "emp-77"}).status_code == 409
    assert api.post("/teachers", w.admin, json={"full_name": "A", "employee_no": "EMP-79"}).status_code == 422
    assert api.post("/teachers", w.admin, json={"full_name": "Bad Phone", "employee_no": "EMP-80", "phone": "abc"}).status_code == 422


def test_teacher_visibility_and_update(api, world):
    w = world
    assert api.get("/teachers", w.admin).json()["total"] == 3
    for u in (w.ua, w.user_a1, w.up1):
        assert api.get("/teachers", u).status_code == 403
        assert api.post("/teachers", u, json={"full_name": "Nope Nope", "employee_no": "X"}).status_code == 403
    me = api.get(f"/teachers/{w.teacher_a.id}", w.ua)
    assert me.status_code == 200 and {a["subject_name"] for a in me.json()["assignments"]} == {"Mathematics", "English"}
    assert api.get(f"/teachers/{w.teacher_b.id}", w.ua).status_code == 404            # teachers cannot browse each other
    assert api.get(f"/teachers/{w.teacher_a.id}", w.user_a1).status_code == 403
    r = api.patch(f"/teachers/{w.teacher_a.id}", w.admin, json={"qualification": "M.Ed", "employee_no": "E1-NEW"})
    assert r.status_code == 200 and r.json()["qualification"] == "M.Ed"
    assert api.patch(f"/teachers/{w.teacher_a.id}", w.admin, json={"employee_no": "E2"}).status_code == 409
    assert api.get("/teachers?q=Teacher B", w.admin).json()["total"] == 1
    assert api.patch(f"/teachers/{w.teacher_c.id}", w.admin, json={"is_active": False}).status_code == 200
    assert api.get("/teachers?is_active=false", w.admin).json()["total"] == 1
    assert login(api, "t.c").status_code == 401


# ------------------------------------------------------------------ students
def test_student_create_with_login_and_parents(api, world):
    w = world
    r = api.post("/students", w.admin, json=student_body(w, parents=[{"parent_id": str(w.parent_1.id), "relation": "father"}]))
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["section_label"] == "Class 8-A" and s["login_id"] == "8a-101" and s["temporary_password"]
    assert s["parents"][0]["full_name"] == "Parent One"
    assert login(api, "8a-101", s["temporary_password"], "mobile").status_code == 200
    # the parent now sees the child
    assert {c["student_id"] for c in api.get("/lookups/my-children", w.up1).json()} >= {s["id"]}
    # without a login
    r = api.post("/students", w.admin, json=student_body(w, roll_no="8A-102", create_login=False))
    assert r.status_code == 201 and r.json()["login_id"] is None and r.json()["temporary_password"] is None


def test_student_create_validation(api, world):
    w = world
    assert api.post("/students", w.admin, json=student_body(w, roll_no="A1")).status_code == 409                    # exists (case-insens.)
    assert api.post("/students", w.admin, json=student_body(w, section_id="00000000-0000-0000-0000-000000000000")).status_code == 422
    assert api.post("/students", w.admin, json=student_body(w, roll_no="bad roll!")).status_code == 422
    assert api.post("/students", w.admin, json=student_body(w, date_of_birth=str(date.today() + timedelta(days=1)))).status_code == 422
    assert api.post("/students", w.admin, json=student_body(w, gender="x")).status_code == 422
    assert api.post("/students", w.admin, json=student_body(w, parents=[{"parent_id": "00000000-0000-0000-0000-000000000000"}])).status_code == 422
    dup = {"parent_id": str(w.parent_1.id)}
    assert api.post("/students", w.admin, json=student_body(w, parents=[dup, dup])).status_code == 422
    for u in (w.ua, w.user_a1, w.up1):
        assert api.post("/students", u, json=student_body(w)).status_code == 403


def test_student_list_scope(api, world):
    w = world
    assert api.get("/students", w.admin).json()["total"] == 6
    assert api.get(f"/students?section_id={w.sec_a.id}", w.admin).json()["total"] == 3
    assert api.get(f"/students?class_id={w.class9.id}", w.admin).json()["total"] == 1
    assert api.get("/students?q=Bilal", w.admin).json()["total"] == 1
    assert api.get("/students?q=B1", w.admin).json()["total"] == 1
    # teacher_a teaches 8-A only; teacher_c teaches nothing
    assert {s["roll_no"] for s in api.get("/students", w.ua).json()["items"]} == {"A1", "A2", "A3"}
    assert api.get("/students", w.uc).json()["total"] == 0
    for u in (w.user_a1, w.up1):
        assert api.get("/students", u).status_code == 403


def test_student_detail_access(api, world):
    w = world
    assert api.get(f"/students/{w.a1.id}", w.user_a1).status_code == 200                 # self
    assert api.get(f"/students/{w.a2.id}", w.user_a1).status_code == 404                 # classmate
    assert api.get(f"/students/{w.a1.id}", w.up1).status_code == 200                      # own child
    assert api.get(f"/students/{w.b2.id}", w.up1).status_code == 404                      # someone else's child
    assert api.get(f"/students/{w.a1.id}", w.ua).status_code == 200                       # teacher of the section
    assert api.get(f"/students/{w.b1.id}", w.ua).status_code == 404                       # other section
    d = api.get(f"/students/{w.a1.id}", w.admin).json()
    assert d["parents"][0]["full_name"] == "Parent One" and d["parents"][0]["phone"]
    assert api.get(f"/students/{w.a1.id}", w.user_a1).json()["parents"][0]["phone"] is None   # phone hidden from the student
    assert api.get("/students/00000000-0000-0000-0000-000000000000", w.admin).status_code == 404


def test_student_update_transfer_and_deactivate(api, world):
    w = world
    r = api.patch(f"/students/{w.a2.id}", w.admin, json={"section_id": str(w.sec_b.id), "full_name": "Bilal K. Khan"})
    assert r.status_code == 200 and r.json()["section_label"] == "Class 8-B"
    assert api.get("/auth/me", w.user_a2).json()["full_name"] == "Bilal K. Khan"              # account name follows
    assert api.patch(f"/students/{w.a2.id}", w.admin, json={"roll_no": "A1"}).status_code == 409
    assert api.patch(f"/students/{w.a2.id}", w.admin, json={"section_id": "00000000-0000-0000-0000-000000000000"}).status_code == 422
    assert api.patch(f"/students/{w.a2.id}", w.ua, json={"full_name": "Hack Hack"}).status_code == 403
    assert api.patch(f"/students/{w.a3.id}", w.admin, json={"is_active": False}).status_code == 200
    assert login(api, "s.a3", platform="mobile").status_code == 401
    assert api.get(f"/students?section_id={w.sec_a.id}&is_active=true", w.admin).json()["total"] == 1


def test_parent_links(api, world):
    w = world
    r = api.post(f"/students/{w.a2.id}/parents", w.admin, json={"parent_id": str(w.parent_2.id), "relation": "mother"})
    assert r.status_code == 201 and r.json()["parents"][0]["relation"] == "mother"
    assert api.post(f"/students/{w.a2.id}/parents", w.admin, json={"parent_id": str(w.parent_2.id)}).status_code == 409
    assert api.post(f"/students/{w.a2.id}/parents", w.admin, json={"parent_id": str(w.parent_2.id), "relation": "uncle"}).status_code == 422
    assert api.get(f"/students/{w.a2.id}", w.up2).status_code == 200                       # access follows the link immediately
    assert api.delete(f"/students/{w.a2.id}/parents/{w.parent_2.id}", w.admin).status_code == 204
    assert api.get(f"/students/{w.a2.id}", w.up2).status_code == 404
    assert api.delete(f"/students/{w.a2.id}/parents/{w.parent_2.id}", w.admin).status_code == 404
    assert api.post(f"/students/{w.a2.id}/parents", w.ua, json={"parent_id": str(w.parent_2.id)}).status_code == 403


def test_create_login_for_existing_student(api, world):
    w = world
    s = api.post("/students", w.admin, json=student_body(w, create_login=False)).json()
    r = api.post(f"/students/{s['id']}/login", w.admin, json={"password": "Chosen789"})
    assert r.status_code == 201 and r.json()["login_id"] == "8a-101"
    assert login(api, "8a-101", "Chosen789", "mobile").status_code == 200
    assert api.post(f"/students/{s['id']}/login", w.admin).status_code == 409


# ------------------------------------------------------------------ parents
def test_parent_create_get_update(api, world):
    w = world
    body = {"full_name": "Naveed Iqbal", "login_id": "naveed.iqbal", "phone": "0333-1234567", "cnic": "37101-1234567-1",
            "occupation": "Shopkeeper", "children": [{"student_id": str(w.a3.id), "relation": "father"}]}
    r = api.post("/parents", w.admin, json=body)
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["children"][0]["roll_no"] == "A3" and p["temporary_password"]
    assert api.get(f"/students/{w.a3.id}", api.post("/auth/login", None, json={"login_id": "naveed.iqbal", "password": p["temporary_password"]},
                                                  headers={"X-Client-Platform": "mobile"}) and w.admin).status_code == 200
    assert api.post("/parents", w.admin, json=dict(body, login_id="other.login")).status_code == 409                   # same CNIC
    assert api.post("/parents", w.admin, json=dict(body, login_id="naveed.iqbal", cnic=None)).status_code == 409        # same login
    assert api.post("/parents", w.admin, json=dict(body, login_id="x.parent", cnic="12345")).status_code == 422
    assert api.post("/parents", w.admin, json=dict(body, login_id="y.parent", cnic=None, children=[{"student_id": "00000000-0000-0000-0000-000000000000"}])).status_code == 422
    assert api.post("/parents", w.admin, json={k: v for k, v in body.items() if k != "phone"} | {"login_id": "z.parent", "cnic": None}).status_code == 422
    r = api.patch(f"/parents/{p['id']}", w.admin, json={"occupation": "Teacher", "address": "Wah Cantt"})
    assert r.status_code == 200 and r.json()["occupation"] == "Teacher"
    assert api.get(f"/parents/{p['id']}", w.admin).json()["children"][0]["full_name"] == "Chand Bibi"
    assert api.get("/parents?q=Naveed", w.admin).json()["total"] == 1
    assert api.get("/parents?q=37101", w.admin).json()["total"] == 1
    for u in (w.ua, w.user_a1, w.up1):
        assert api.get("/parents", u).status_code == 403
        assert api.get(f"/parents/{p['id']}", u).status_code == 403
    assert api.patch(f"/parents/{p['id']}", w.admin, json={"is_active": False}).status_code == 200
