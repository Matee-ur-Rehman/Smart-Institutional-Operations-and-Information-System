from datetime import timedelta

API_EVENTS = "/events"


def mk(api, w, **kw):
    body = {"title": "Sports Day", "event_type": "sports", "start_date": str(w.today + timedelta(days=5)), "notify": False}
    body.update(kw)
    return api.post(API_EVENTS, w.admin, json=body)


def test_admin_creates_event_defaults_end_date(api, world):
    r = mk(api, world)
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["end_date"] == j["start_date"] and j["audience"] == "all" and j["audience_label"] == "Everyone"


def test_only_admin_can_write(api, world):
    for u in (world.ua, world.user_a1, world.up1):
        assert api.post(API_EVENTS, u, json={"title": "Hack", "start_date": str(world.today)}).status_code == 403
    eid = mk(api, world).json()["id"]
    assert api.patch(f"{API_EVENTS}/{eid}", world.ua, json={"title": "Nope"}).status_code == 403
    assert api.delete(f"{API_EVENTS}/{eid}", world.ua).status_code == 403


def test_validation(api, world):
    w = world
    assert mk(api, w, title="ab").status_code == 422
    assert mk(api, w, end_date=str(w.today - timedelta(days=30))).status_code == 422
    assert mk(api, w, audience="class").status_code == 422                       # no section
    assert mk(api, w, audience="class", section_id="00000000-0000-0000-0000-000000000001").status_code == 422
    assert mk(api, w, start_time="10:00", end_time="09:00").status_code == 422
    assert mk(api, w, event_type="party").status_code == 422


def test_audience_visibility(api, world):
    w = world
    mk(api, w, title="For everyone")
    mk(api, w, title="Teachers only", audience="teachers")
    mk(api, w, title="Students only", audience="students")
    mk(api, w, title="Parents only", audience="parents")
    mk(api, w, title="Section 8A", audience="class", section_id=str(w.sec_a.id))
    mk(api, w, title="Section 9A", audience="class", section_id=str(w.sec_9a.id))

    def titles(u):
        r = api.get(API_EVENTS, u)
        assert r.status_code == 200
        return {e["title"] for e in r.json()["items"]}

    assert len(titles(w.admin)) == 6
    assert titles(w.ua) == {"For everyone", "Teachers only", "Section 8A"}
    assert titles(w.uc) == {"For everyone", "Teachers only"}            # teacher with no classes
    assert titles(w.user_a1) == {"For everyone", "Students only", "Section 8A"}
    assert titles(w.user_c1) == {"For everyone", "Students only", "Section 9A"}
    assert titles(w.up1) == {"For everyone", "Parents only", "Section 8A"}   # child in 8-A
    assert titles(w.up2) == {"For everyone", "Parents only"}


def test_get_hidden_event_is_404(api, world):
    eid = mk(api, world, audience="teachers").json()["id"]
    assert api.get(f"{API_EVENTS}/{eid}", world.user_a1).status_code == 404
    assert api.get(f"{API_EVENTS}/{eid}", world.ua).status_code == 200


def test_filters_month_and_type(api, world):
    w = world
    mk(api, w, title="Holiday", event_type="holiday", start_date="2027-03-23")
    mk(api, w, title="Meeting", event_type="meeting", start_date="2027-04-02", end_date="2027-04-03")
    r = api.get(API_EVENTS + "?month=2027-03", w.admin).json()
    assert [e["title"] for e in r["items"]] == ["Holiday"]
    r = api.get(API_EVENTS + "?month=2027-04&event_type=meeting", w.admin).json()
    assert r["total"] == 1
    assert api.get(API_EVENTS + "?month=2027-13", w.admin).status_code == 422
    assert api.get(API_EVENTS + "?event_type=holiday", w.admin).json()["total"] == 1
    # multi-day overlap
    assert api.get(API_EVENTS + "?from_date=2027-04-03&to_date=2027-04-10", w.admin).json()["total"] == 1


def test_update_and_delete(api, world):
    w = world
    eid = mk(api, w, audience="class", section_id=str(w.sec_a.id)).json()["id"]
    r = api.patch(f"{API_EVENTS}/{eid}", w.admin, json={"title": "Renamed Event", "audience": "all"})
    assert r.status_code == 200 and r.json()["title"] == "Renamed Event" and r.json()["section_id"] is None
    assert api.patch(f"{API_EVENTS}/{eid}", w.admin, json={"audience": "class"}).status_code == 422
    assert api.patch(f"{API_EVENTS}/{eid}", w.admin, json={"end_date": "2000-01-01"}).status_code == 422
    assert api.delete(f"{API_EVENTS}/{eid}", w.admin).status_code == 204
    assert api.get(f"{API_EVENTS}/{eid}", w.admin).status_code == 404


def test_notify_flag(api, world):
    w = world
    mk(api, w, title="Silent", notify=False)
    assert api.get("/notifications/unread-count", w.user_a1).json()["count"] == 0
    mk(api, w, title="Loud one", notify=True)
    n = api.get("/notifications", w.user_a1).json()["items"]
    assert len(n) == 1 and n[0]["type"] == "event" and "Loud one" in n[0]["title"]
    assert api.get("/notifications/unread-count", w.admin).json()["count"] == 0   # admin is not in 'all'
