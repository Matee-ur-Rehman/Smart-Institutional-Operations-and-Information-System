"""Leave requests: apply, decide, cancel, visibility, effect on attendance."""
from datetime import timedelta

from tests.foundation.test_attendance import put, school_day


NOBODY = object()


def apply(api, w, child=None, user=None, start=1, days=2, **kw):
    child = child or w.a1
    body = {"student_id": str(child.id), "from_date": str(w.today + timedelta(days=start)),
            "to_date": str(w.today + timedelta(days=start + days - 1)), "leave_type": "sick", "reason": "Fever and rest advised"}
    body.update(kw)
    return api.post("/leave-requests", None if user is NOBODY else (user or w.up1), json=body)


def test_parent_applies_and_staff_are_notified(api, world):
    w = world
    r = apply(api, w)
    assert r.status_code == 201, r.text
    lr = r.json()
    assert lr["status"] == "pending" and lr["days"] == 2 and lr["student_name"] == "Ali Ahmed"
    assert api.get("/notifications/unread-count", w.admin).json()["count"] == 1
    assert api.get("/notifications/unread-count", w.ua).json()["count"] == 1     # teaches 8-A
    assert api.get("/notifications/unread-count", w.ub).json()["count"] == 0     # teaches 8-B only


def test_apply_validation_and_rules(api, world):
    w = world
    assert apply(api, w, reason="no").status_code == 422
    assert apply(api, w, leave_type="vacation").status_code == 422
    bad = apply(api, w, to_date=str(w.today - timedelta(days=30)))
    assert bad.status_code == 422
    assert apply(api, w, start=-20, days=2).status_code == 422                    # too far in the past
    assert apply(api, w, start=1, days=40).status_code == 422                     # longer than 30 days
    assert apply(api, w, child=w.b2).status_code == 404                           # not their child
    assert apply(api, w, user=w.user_a1).status_code == 403                       # students cannot apply
    assert apply(api, w, user=w.ua).status_code == 403
    assert apply(api, w, user=NOBODY).status_code == 401


def test_overlap_is_rejected_but_rejected_leave_can_be_reapplied(api, world):
    w = world
    first = apply(api, w, start=1, days=3).json()
    assert apply(api, w, start=2, days=2).status_code == 409
    assert apply(api, w, child=w.b1, start=2, days=2).status_code == 201          # different child
    api.post(f"/leave-requests/{first['id']}/reject", w.admin, json={"note": "Please attach a medical note"})
    assert apply(api, w, start=2, days=2).status_code == 201


def test_approve_flow_notifies_parent(api, world):
    w = world
    lr = apply(api, w).json()
    r = api.post(f"/leave-requests/{lr['id']}/approve", w.ua, json={"note": "Get well soon"})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    assert r.json()["decided_by_name"] == "Teacher A" and r.json()["decision_note"] == "Get well soon"
    assert api.post(f"/leave-requests/{lr['id']}/approve", w.admin).status_code == 409      # already decided
    assert api.post(f"/leave-requests/{lr['id']}/cancel", w.up1).status_code == 409
    items = api.get("/notifications", w.up1).json()["items"]
    assert any(n["type"] == "leave" and "approved" in n["body"] for n in items)


def test_reject_requires_a_reason(api, world):
    w = world
    lr = apply(api, w).json()
    assert api.post(f"/leave-requests/{lr['id']}/reject", w.admin, json={}).status_code == 422
    assert api.post(f"/leave-requests/{lr['id']}/reject", w.admin, json={"note": "x"}).status_code == 422
    r = api.post(f"/leave-requests/{lr['id']}/reject", w.admin, json={"note": "Exams that week"})
    assert r.json()["status"] == "rejected"


def test_only_the_right_staff_can_decide(api, world):
    w = world
    lr = apply(api, w).json()
    assert api.post(f"/leave-requests/{lr['id']}/approve", w.ub).status_code == 404        # not their section
    assert api.post(f"/leave-requests/{lr['id']}/approve", w.uc).status_code == 404
    for u in (w.up1, w.user_a1):
        assert api.post(f"/leave-requests/{lr['id']}/approve", u).status_code == 403
        assert api.post(f"/leave-requests/{lr['id']}/reject", u, json={"note": "no way"}).status_code == 403


def test_parent_can_cancel_only_own_pending(api, world):
    w = world
    lr = apply(api, w).json()
    assert api.post(f"/leave-requests/{lr['id']}/cancel", w.up2).status_code == 404
    assert api.post(f"/leave-requests/{lr['id']}/cancel", w.ua).status_code == 403
    r = api.post(f"/leave-requests/{lr['id']}/cancel", w.up1)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert api.post(f"/leave-requests/{lr['id']}/cancel", w.up1).status_code == 409


def test_listing_scopes_and_filters(api, world):
    w = world
    apply(api, w, child=w.a1)
    apply(api, w, child=w.b1)
    apply(api, w, child=w.b2, user=w.up2)
    assert api.get("/leave-requests", w.admin).json()["total"] == 3
    assert api.get("/leave-requests", w.up1).json()["total"] == 2
    assert api.get("/leave-requests", w.up2).json()["total"] == 1
    assert api.get("/leave-requests", w.ua).json()["total"] == 1                    # 8-A only
    assert api.get("/leave-requests", w.ub).json()["total"] == 2                    # 8-B: b1 and b2
    assert api.get("/leave-requests", w.uc).json()["total"] == 0
    assert api.get("/leave-requests", w.user_a1).status_code == 403
    assert api.get(f"/leave-requests?section_id={w.sec_b.id}", w.admin).json()["total"] == 2
    assert api.get("/leave-requests?status=approved", w.admin).json()["total"] == 0
    first = api.get("/leave-requests", w.up2).json()["items"][0]["id"]
    assert api.get(f"/leave-requests/{first}", w.up1).status_code == 404            # another family's request
    assert api.get(f"/leave-requests/{first}", w.up2).status_code == 200


def test_approval_converts_past_absences_and_prefills_sheet(api, world):
    w = world
    d = school_day(w.today, back=1)
    put(api, w.admin, w, w.sec_a, [(w.a1, "absent")], d)
    lr = api.post("/leave-requests", w.up1, json={
        "student_id": str(w.a1.id), "from_date": str(d), "to_date": str(w.today + timedelta(days=2)),
        "leave_type": "sick", "reason": "Was unwell, doctor note attached"})
    assert lr.status_code == 201, lr.text
    api.post(f"/leave-requests/{lr.json()['id']}/approve", w.admin)
    rows = api.get(f"/attendance/sections/{w.sec_a.id}?date={d}", w.ua).json()["rows"]
    a1 = [r for r in rows if r["roll_no"] == "A1"][0]
    assert a1["status"] == "leave" and a1["on_approved_leave"] is True            # absence became approved leave
    tomorrow = api.get(f"/attendance/sections/{w.sec_a.id}?date={w.today + timedelta(days=1)}", w.ua).json()["rows"]
    assert [r for r in tomorrow if r["roll_no"] == "A1"][0]["on_approved_leave"] is True
    assert [r for r in tomorrow if r["roll_no"] == "A2"][0]["on_approved_leave"] is False
