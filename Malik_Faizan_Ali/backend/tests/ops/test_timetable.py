"""Timetable: periods, slots, clash detection, role views."""


def mk_period(api, w, no, start, end, **kw):
    r = api.post("/period-definitions", w.admin, json={"period_no": no, "start_time": start, "end_time": end,
                                                       "label": kw.pop("label", f"Period {no}"), **kw})
    assert r.status_code == 201, r.text
    return r.json()


def slot(w, p, **kw):
    d = {"section_id": str(w.sec_a.id), "subject_id": str(w.math.id), "day_of_week": 1, "period_id": p["id"], "room": "R-8A"}
    d.update(kw)
    return d


def test_period_crud_and_validation(api, world):
    w = world
    p1 = mk_period(api, w, 1, "08:00", "08:40")
    assert api.post("/period-definitions", w.admin, json={"period_no": 1, "start_time": "09:00", "end_time": "09:40", "label": "dup"}).status_code == 409
    assert api.post("/period-definitions", w.admin, json={"period_no": 2, "start_time": "08:30", "end_time": "09:00", "label": "ovl"}).status_code == 409
    assert api.post("/period-definitions", w.admin, json={"period_no": 3, "start_time": "10:00", "end_time": "09:00", "label": "bad"}).status_code == 422
    assert api.post("/period-definitions", w.ua, json={"period_no": 4, "start_time": "11:00", "end_time": "11:40", "label": "x"}).status_code == 403
    assert api.get("/period-definitions", w.user_a1).status_code == 200
    r = api.patch(f"/period-definitions/{p1['id']}", w.admin, json={"label": "Assembly"})
    assert r.status_code == 200 and r.json()["label"] == "Assembly"


def test_slot_creation_resolves_teacher_and_blocks_clashes(api, world):
    w = world
    p1 = mk_period(api, w, 1, "08:00", "08:40")
    r = api.post("/timetable-slots", w.admin, json=slot(w, p1))
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["teacher_name"] == "Teacher A" and s["period_no"] == 1
    # same section, day and period twice
    assert api.post("/timetable-slots", w.admin, json=slot(w, p1, subject_id=str(w.english.id))).status_code == 409
    # teacher_a already busy in that period (explicit teacher in another section he does not teach -> validation/conflict)
    r = api.post("/timetable-slots", w.admin, json=slot(w, p1, section_id=str(w.sec_b.id), teacher_id=s["teacher_id"]))
    assert r.status_code in (400, 409, 422)
    # section 8-B with its own teacher is fine at the same time
    r = api.post("/timetable-slots", w.admin, json=slot(w, p1, section_id=str(w.sec_b.id)))
    assert r.status_code == 201, r.text
    # day 7 invalid
    assert api.post("/timetable-slots", w.admin, json=slot(w, p1, day_of_week=7)).status_code == 422


def test_only_admin_writes_slots(api, world):
    w = world
    p1 = mk_period(api, w, 1, "08:00", "08:40")
    for u in (w.ua, w.user_a1, w.up1):
        assert api.post("/timetable-slots", u, json=slot(w, p1)).status_code == 403
    assert api.post("/timetable-slots", None, json=slot(w, p1)).status_code == 401


def test_views_per_role(api, world):
    w = world
    p1 = mk_period(api, w, 1, "08:00", "08:40")
    p2 = mk_period(api, w, 2, "08:40", "09:20")
    api.post("/timetable-slots", w.admin, json=slot(w, p1))
    api.post("/timetable-slots", w.admin, json=slot(w, p2, subject_id=str(w.english.id), day_of_week=2))
    api.post("/timetable-slots", w.admin, json=slot(w, p1, section_id=str(w.sec_b.id)))

    sec = api.get(f"/timetable/sections/{w.sec_a.id}", w.admin)
    assert sec.status_code == 200
    me_student = api.get("/timetable/me", w.user_a1)
    assert me_student.status_code == 200
    me_teacher = api.get("/timetable/me", w.ua)
    assert me_teacher.status_code == 200
    assert api.get("/timetable/me", w.up1).status_code == 403          # parents use /students/{id}
    assert api.get(f"/timetable/students/{w.a1.id}", w.up1).status_code == 200
    assert api.get(f"/timetable/students/{w.c1.id}", w.up1).status_code == 404   # not their child
    assert api.get(f"/timetable/students/{w.b1.id}", w.user_a1).status_code in (403, 404)
    assert api.get(f"/timetable/teachers/{w.teacher_a.id}", w.admin).status_code == 200
    assert api.get(f"/timetable/teachers/{w.teacher_a.id}", w.ub).status_code in (403, 404)


def test_slot_update_delete_and_period_in_use(api, world):
    w = world
    p1 = mk_period(api, w, 1, "08:00", "08:40")
    s = api.post("/timetable-slots", w.admin, json=slot(w, p1)).json()
    assert api.delete(f"/period-definitions/{p1['id']}", w.admin).status_code == 409   # in use
    r = api.patch(f"/timetable-slots/{s['id']}", w.admin, json={"room": "Lab-1"})
    assert r.status_code == 200 and r.json()["room"] == "Lab-1"
    assert api.delete(f"/timetable-slots/{s['id']}", w.admin).status_code == 204
    assert api.delete(f"/period-definitions/{p1['id']}", w.admin).status_code == 204
