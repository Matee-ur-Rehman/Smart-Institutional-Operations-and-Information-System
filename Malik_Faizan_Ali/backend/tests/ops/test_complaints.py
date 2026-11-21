C = "/complaints"


def mk(api, w, user=None, **kw):
    body = {"category": "academic", "subject": "Homework load", "description": "Too much homework every day."}
    body.update(kw)
    return api.post(C, user or w.up1, json=body)


def test_parent_submits_ticket(api, world):
    w = world
    r = mk(api, w, student_id=str(w.a1.id))
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["ticket_no"].startswith("CMP-") and j["status"] == "open" and j["priority"] == "normal"
    assert j["student_name"] == "Ali Ahmed" and j["comments"] == []
    assert mk(api, w).json()["ticket_no"] != j["ticket_no"]
    # admins are notified
    assert api.get("/notifications/unread-count", w.admin).json()["count"] == 2


def test_only_parents_submit(api, world):
    w = world
    for u in (w.admin, w.ua, w.user_a1):
        assert mk(api, w, user=u).status_code == 403


def test_validation_and_foreign_child(api, world):
    w = world
    assert mk(api, w, subject="ab").status_code == 422
    assert mk(api, w, description="short").status_code == 422
    assert mk(api, w, category="weather").status_code == 422
    assert mk(api, w, kind="rant").status_code == 422
    assert mk(api, w, student_id=str(w.b2.id)).status_code == 404       # not parent_1's child
    assert mk(api, w, student_id=str(w.b1.id)).status_code == 201       # in a different section, still theirs
    assert mk(api, w, kind="feedback", category="facility").status_code == 201
    assert mk(api, w, kind="suggestion").status_code == 201


def test_visibility(api, world):
    w = world
    t1 = mk(api, w, user=w.up1).json()["id"]
    t2 = mk(api, w, user=w.up2, subject="Fee query").json()["id"]
    assert [i["id"] for i in api.get(C, w.up1).json()["items"]] == [t1]
    assert [i["id"] for i in api.get(C, w.up2).json()["items"]] == [t2]
    assert api.get(C, w.admin).json()["total"] == 2
    assert api.get(f"{C}/{t2}", w.up1).status_code == 404
    assert api.get(f"{C}/{t2}", w.admin).status_code == 200
    # teachers and students have no access to complaints at all
    for u in (w.ua, w.user_a1):
        assert api.get(C, u).status_code == 403
        assert api.get(f"{C}/{t1}", u).status_code == 403
    assert api.patch(f"{C}/{t1}", w.up1, json={"status": "closed"}).status_code == 403
    assert api.get(C + "/summary", w.up1).status_code == 403


def test_status_workflow_and_notifications(api, world):
    w = world
    tid = mk(api, w).json()["id"]
    r = api.patch(f"{C}/{tid}", w.admin, json={"status": "in_review", "priority": "high", "assigned_to": str(w.ua.id)})
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "in_review" and j["priority"] == "high" and j["assigned_to_name"] == "Teacher A"
    n = api.get("/notifications", w.up1).json()["items"]
    assert len(n) == 1 and "In review" in n[0]["title"]
    api.patch(f"{C}/{tid}", w.admin, json={"priority": "low"})            # no status change: no new notification
    assert api.get("/notifications/unread-count", w.up1).json()["count"] == 1
    assert api.patch(f"{C}/{tid}", w.admin, json={"status": "resolved"}).json()["status"] == "resolved"
    assert api.get("/notifications/unread-count", w.up1).json()["count"] == 2
    assert api.patch(f"{C}/{tid}", w.admin, json={"status": "bogus"}).status_code == 422
    assert api.patch(f"{C}/{tid}", w.admin, json={"assigned_to": str(w.user_a1.id)}).status_code == 422
    assert api.patch(f"{C}/{tid}", w.admin, json={"assigned_to": "00000000-0000-0000-0000-000000000009"}).status_code == 422


def test_comments_internal_notes_and_closed(api, world):
    w = world
    tid = mk(api, w).json()["id"]
    assert api.post(f"{C}/{tid}/comments", w.admin, json={"message": "Looking into it"}).status_code == 201
    assert api.post(f"{C}/{tid}/comments", w.admin, json={"message": "Staff only", "is_internal": True}).status_code == 201
    r = api.post(f"{C}/{tid}/comments", w.up1, json={"message": "Thanks", "is_internal": True})   # forced public
    assert r.status_code == 201
    admin_view = api.get(f"{C}/{tid}", w.admin).json()
    parent_view = api.get(f"{C}/{tid}", w.up1).json()
    assert len(admin_view["comments"]) == 3 and admin_view["comment_count"] == 3
    assert [c["message"] for c in parent_view["comments"]] == ["Looking into it", "Thanks"]
    assert parent_view["comment_count"] == 2
    assert all(not c["is_internal"] for c in parent_view["comments"])
    # notifications: admin reply -> parent (public only); parent reply -> admins
    assert api.get("/notifications/unread-count", w.up1).json()["count"] == 1
    assert api.get("/notifications/unread-count", w.admin).json()["count"] == 2     # new ticket + parent reply
    assert api.post(f"{C}/{tid}/comments", w.up2, json={"message": "Not mine"}).status_code == 404
    assert api.post(f"{C}/{tid}/comments", w.up1, json={"message": ""}).status_code == 422
    api.patch(f"{C}/{tid}", w.admin, json={"status": "closed"})
    assert api.post(f"{C}/{tid}/comments", w.up1, json={"message": "More"}).status_code == 409


def test_filters_and_summary(api, world):
    w = world
    a = mk(api, w, category="fee", kind="feedback").json()["id"]
    mk(api, w, category="academic")
    mk(api, w, user=w.up2, category="fee")
    api.patch(f"{C}/{a}", w.admin, json={"status": "resolved", "assigned_to": str(w.admin.id)})
    assert api.get(C + "?category=fee", w.admin).json()["total"] == 2
    assert api.get(C + "?kind=feedback", w.admin).json()["total"] == 1
    assert api.get(C + "?status=resolved", w.admin).json()["total"] == 1
    assert api.get(C + f"?assigned_to={w.admin.id}", w.admin).json()["total"] == 1
    assert api.get(C + "?category=fee", w.up1).json()["total"] == 1       # filters stay scoped
    s = api.get(C + "/summary", w.admin).json()
    assert s["total"] == 3 and s["by_status"]["open"] == 2 and s["by_status"]["resolved"] == 1
    assert s["by_category"]["fee"] == 2 and s["by_kind"]["feedback"] == 1 and s["unassigned_open"] == 2
