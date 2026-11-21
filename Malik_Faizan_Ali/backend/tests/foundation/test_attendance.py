"""Attendance: daily sheets, bulk marking, rules, summaries and visibility."""
from datetime import timedelta


def school_day(today, back=0):
    """A non-Sunday date `back` or more days before today (tests must not depend on the weekday they run on)."""
    d = today - timedelta(days=back)
    while d.weekday() == 6:
        d -= timedelta(days=1)
    return d


def put(api, user, w, section, entries, d=None):
    q = f"?date={d}" if d else ""
    return api.put(f"/attendance/sections/{section.id}{q}", user, json={"entries": [
        {"student_id": str(s.id), "status": st, **({"remarks": r[0]} if (r := rest) else {})} for s, st, *rest in entries]})


def test_sheet_lists_active_students_unmarked(api, world):
    w = world
    d = school_day(w.today)
    r = api.get(f"/attendance/sections/{w.sec_a.id}?date={d}", w.ua)
    assert r.status_code == 200, r.text
    sheet = r.json()
    assert sheet["total"] == 3 and sheet["marked"] == 0 and sheet["editable"] is True
    assert [x["roll_no"] for x in sheet["rows"]] == ["A1", "A2", "A3"]
    assert all(x["status"] is None for x in sheet["rows"])


def test_teacher_marks_and_updates(api, world):
    w = world
    d = school_day(w.today)
    r = put(api, w.ua, w, w.sec_a, [(w.a1, "present"), (w.a2, "absent"), (w.a3, "late")], d)
    assert r.status_code == 200, r.text
    assert r.json()["counts"] == {"present": 1, "absent": 1, "late": 1, "leave": 0} and r.json()["marked"] == 3
    r = put(api, w.ua, w, w.sec_a, [(w.a2, "present")], d)                      # correction: upsert, no duplicate row
    assert r.json()["counts"]["absent"] == 0 and r.json()["counts"]["present"] == 2


def test_validation_and_rules(api, world):
    w = world
    d = school_day(w.today)
    assert put(api, w.ua, w, w.sec_a, [(w.a1, "sleeping")], d).status_code == 422
    assert put(api, w.ua, w, w.sec_a, [(w.b1, "present")], d).status_code == 422          # other section
    assert put(api, w.ua, w, w.sec_a, [(w.a1, "present"), (w.a1, "absent")], d).status_code == 422   # duplicate
    assert put(api, w.ua, w, w.sec_a, [(w.a1, "present")], w.today + timedelta(days=1)).status_code == 400   # future
    sunday = w.today
    while sunday.weekday() != 6:
        sunday -= timedelta(days=1)
    assert put(api, w.admin, w, w.sec_a, [(w.a1, "present")], sunday).json()["code"] == "not_school_day"
    r = api.put(f"/attendance/sections/{w.sec_a.id}", w.ua, json={"entries": []})
    assert r.status_code == 422


def test_holiday_blocks_marking(api, world):
    w = world
    d = school_day(w.today, back=1)
    ev = api.post("/events", w.admin, json={"title": "Public holiday", "event_type": "holiday", "start_date": str(d),
                                           "end_date": str(d), "audience": "all"})
    assert ev.status_code == 201, ev.text
    r = put(api, w.admin, w, w.sec_a, [(w.a1, "present")], d)
    assert r.status_code == 400 and r.json()["code"] == "holiday"
    assert api.get(f"/attendance/sections/{w.sec_a.id}?date={d}", w.admin).json()["editable"] is False


def test_teacher_scope_and_edit_window(api, world):
    w = world
    d = school_day(w.today)
    assert put(api, w.ub, w, w.sec_a, [(w.a1, "present")], d).status_code == 404          # teaches 8-B only
    assert put(api, w.uc, w, w.sec_a, [(w.a1, "present")], d).status_code == 404
    old = school_day(w.today, back=10)
    assert put(api, w.ua, w, w.sec_a, [(w.a1, "present")], old).status_code == 403          # beyond 7 days
    assert put(api, w.admin, w, w.sec_a, [(w.a1, "present")], old).status_code == 200      # admin may correct it
    assert api.get(f"/attendance/sections/{w.sec_a.id}", w.ub).status_code == 404


def test_students_and_parents_cannot_mark(api, world):
    w = world
    for u in (w.user_a1, w.up1):
        assert put(api, u, w, w.sec_a, [(w.a1, "present")]).status_code == 403
        assert api.get(f"/attendance/sections/{w.sec_a.id}", u).status_code == 403
    assert api.get(f"/attendance/sections/{w.sec_a.id}").status_code == 401


def test_absent_notifies_parent_once(api, world):
    w = world
    d = w.today if w.today.weekday() != 6 else None
    if d is None:
        return                                                                        # notifications are only sent for today
    put(api, w.ua, w, w.sec_a, [(w.a1, "absent")], d)
    assert api.get("/notifications/unread-count", w.up1).json()["count"] == 1
    put(api, w.ua, w, w.sec_a, [(w.a1, "absent")], d)                                 # same value again: no second alert
    assert api.get("/notifications/unread-count", w.up1).json()["count"] == 1
    n = api.get("/notifications", w.up1).json()["items"][0]
    assert n["type"] == "attendance"
    assert api.get("/notifications/unread-count", w.up2).json()["count"] == 0        # unrelated family


def test_student_summary_and_percentage(api, world):
    w = world
    days = [school_day(w.today, back=i) for i in range(0, 12)]
    days = sorted(set(days))[-5:]
    plan = ["present", "present", "late", "absent", "leave"]
    for d, st in zip(days, plan):
        put(api, w.admin, w, w.sec_a, [(w.a1, st)], d)
    r = api.get(f"/attendance/students/{w.a1.id}?from_date={days[0]}&to_date={days[-1]}", w.user_a1)
    assert r.status_code == 200, r.text
    s = r.json()["summary"]
    assert (s["present"], s["late"], s["absent"], s["leave"], s["total_days"]) == (2, 1, 1, 1, 5)
    assert float(s["percentage"]) == 75.0                         # (2+1)/(2+1+1); leave day excluded
    assert len(r.json()["records"]) == 5
    me = api.get(f"/attendance/me?from_date={days[0]}&to_date={days[-1]}", w.user_a1)
    assert me.status_code == 200 and me.json()["summary"]["total_days"] == 5
    assert api.get("/attendance/me", w.up1).status_code == 403


def test_visibility_of_student_attendance(api, world):
    w = world
    assert api.get(f"/attendance/students/{w.a1.id}", w.up1).status_code == 200          # own child
    assert api.get(f"/attendance/students/{w.a1.id}", w.up2).status_code == 404         # other family
    assert api.get(f"/attendance/students/{w.a1.id}", w.user_a2).status_code == 404     # classmate
    assert api.get(f"/attendance/students/{w.a1.id}", w.ua).status_code == 200          # teacher of the section
    assert api.get(f"/attendance/students/{w.a1.id}", w.ub).status_code == 404
    assert api.get(f"/attendance/students/{w.a1.id}", w.admin).status_code == 200
    r = api.get(f"/attendance/students/{w.a1.id}?from_date=2026-01-10&to_date=2026-01-01", w.admin)
    assert r.status_code == 422
    r = api.get(f"/attendance/students/{w.a1.id}?from_date=2020-01-01&to_date=2026-01-01", w.admin)
    assert r.status_code == 422


def test_section_summary_and_overview(api, world):
    w = world
    d = school_day(w.today)
    put(api, w.ua, w, w.sec_a, [(w.a1, "present"), (w.a2, "absent"), (w.a3, "present")], d)
    s = api.get(f"/attendance/sections/{w.sec_a.id}/summary?from_date={d}&to_date={d}", w.ua).json()
    assert len(s["students"]) == 3 and s["low_attendance_count"] == 1
    assert [x for x in s["students"] if x["roll_no"] == "A2"][0]["low_attendance"] is True
    assert api.get(f"/attendance/sections/{w.sec_a.id}/summary", w.ub).status_code == 404
    ov = api.get(f"/attendance/overview?date={d}", w.admin).json()
    marked = {x["section_label"]: x["is_marked"] for x in ov["sections"]}
    assert sum(marked.values()) == 1 and ov["unmarked_sections"] == 2
    assert [x["section_id"] for x in api.get(f"/attendance/overview?date={d}", w.ub).json()["sections"]] == [str(w.sec_b.id)]
    assert api.get("/attendance/overview", w.up1).status_code == 403
