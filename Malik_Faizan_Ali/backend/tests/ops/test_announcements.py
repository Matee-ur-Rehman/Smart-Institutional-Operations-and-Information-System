from datetime import datetime, timedelta, timezone

A = "/announcements"


def now():
    return datetime.now(timezone.utc)


def mk(api, w, **kw):
    body = {"title": "Notice", "body": "School closed tomorrow."}
    body.update(kw)
    return api.post(A, w.admin, json=body)


def test_create_publishes_and_notifies_all(api, world):
    w = world
    r = mk(api, w)
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["status"] == "published" and j["target_label"] == "Everyone" and not j["is_expired"]
    for u in (w.ua, w.user_a1, w.up1, w.up2):
        assert api.get("/notifications/unread-count", u).json()["count"] == 1
    assert api.get("/notifications/unread-count", w.admin).json()["count"] == 0


def test_only_admin_writes(api, world):
    for u in (world.ua, world.user_a1, world.up1):
        assert api.post(A, u, json={"title": "Fake", "body": "x"}).status_code == 403


def test_validation(api, world):
    w = world
    assert mk(api, w, title="x").status_code == 422
    assert mk(api, w, body="").status_code == 422
    assert mk(api, w, audience="class").status_code == 422
    assert mk(api, w, audience="class", section_id="00000000-0000-0000-0000-000000000001").status_code == 422
    assert mk(api, w, audience="class", class_id="00000000-0000-0000-0000-000000000001").status_code == 422
    assert mk(api, w, priority="critical").status_code == 422
    assert mk(api, w, publish_at=now().isoformat(), expires_at=(now() - timedelta(days=1)).isoformat()).status_code == 422


def test_audience_targeting_and_visibility(api, world):
    w = world
    mk(api, w, title="Everyone A")
    mk(api, w, title="Teachers A", audience="teachers")
    mk(api, w, title="Students A", audience="students")
    mk(api, w, title="Parents A", audience="parents")
    mk(api, w, title="Section 8A", audience="class", section_id=str(w.sec_a.id))
    mk(api, w, title="Class 9", audience="class", class_id=str(w.class9.id))
    mk(api, w, title="Class 8", audience="class", class_id=str(w.class8.id))

    def titles(u):
        return {a["title"] for a in api.get(A, u).json()["items"]}

    assert titles(w.user_a1) == {"Everyone A", "Students A", "Section 8A", "Class 8"}
    assert titles(w.user_b1) == {"Everyone A", "Students A", "Class 8"}
    assert titles(w.user_c1) == {"Everyone A", "Students A", "Class 9"}
    assert titles(w.up1) == {"Everyone A", "Parents A", "Section 8A", "Class 8"}
    assert titles(w.ua) == {"Everyone A", "Teachers A", "Section 8A", "Class 8"}
    assert titles(w.uc) == {"Everyone A", "Teachers A"}
    assert len(titles(w.admin)) == 7
    # notifications follow the same targeting
    assert api.get("/notifications/unread-count", w.user_c1).json()["count"] == 3
    assert api.get("/notifications/unread-count", w.uc).json()["count"] == 2


def test_draft_hidden_then_published_notifies_once(api, world):
    w = world
    aid = mk(api, w, title="Draft one", status="draft").json()["id"]
    assert api.get(A, w.user_a1).json()["total"] == 0
    assert api.get(f"{A}/{aid}", w.user_a1).status_code == 404
    assert api.get(A + "?status=draft", w.admin).json()["total"] == 1
    assert api.get("/notifications/unread-count", w.user_a1).json()["count"] == 0
    r = api.patch(f"{A}/{aid}", w.admin, json={"status": "published"})
    assert r.status_code == 200 and r.json()["status"] == "published"
    assert api.get("/notifications/unread-count", w.user_a1).json()["count"] == 1
    api.patch(f"{A}/{aid}", w.admin, json={"priority": "urgent"})       # edit again: no second blast
    assert api.get("/notifications/unread-count", w.user_a1).json()["count"] == 1


def test_scheduled_publish_and_expiry(api, world):
    w = world
    mk(api, w, title="Later", publish_at=(now() + timedelta(days=2)).isoformat())
    assert api.get(A, w.user_a1).json()["total"] == 0
    assert api.get("/notifications/unread-count", w.user_a1).json()["count"] == 0
    # expired one (created directly because the API rejects expires<=publish; publish in the past is fine)
    mk(api, w, title="Old", publish_at=(now() - timedelta(days=3)).isoformat(),
       expires_at=(now() - timedelta(days=1)).isoformat())
    assert api.get(A, w.user_a1).json()["total"] == 0
    assert api.get(A, w.admin).json()["total"] == 0                       # default feed = live only (contract)
    assert api.get(A + "?status=published", w.admin).json()["total"] == 2   # admin can still see them


def test_urgent_prefix_and_long_body_truncated(api, world):
    w = world
    mk(api, w, title="Flood", priority="urgent", body="x" * 500)
    n = api.get("/notifications", w.user_a1).json()["items"][0]
    assert n["title"].startswith("URGENT: ") and len(n["body"]) <= 200


def test_archive_delete_rules(api, world):
    w = world
    aid = mk(api, w).json()["id"]
    assert api.delete(f"{A}/{aid}", w.admin).status_code == 409           # published: archive instead
    r = api.post(f"{A}/{aid}/archive", w.admin)
    assert r.status_code == 200 and r.json()["status"] == "archived"
    assert api.get(A, w.user_a1).json()["total"] == 0
    assert api.patch(f"{A}/{aid}", w.admin, json={"title": "Edit after"}).status_code == 409
    assert api.delete(f"{A}/{aid}", w.admin).status_code == 204
    assert api.get(f"{A}/{aid}", w.admin).status_code == 404


def test_filters(api, world):
    w = world
    mk(api, w, title="Normal one")
    mk(api, w, title="Urgent one", priority="urgent")
    assert api.get(A + "?priority=urgent", w.user_a1).json()["total"] == 1
    assert api.get(A + "?audience=teachers", w.admin).json()["total"] == 0
    r = api.get(A + "?page_size=1&page=2", w.admin).json()
    assert r["total"] == 2 and len(r["items"]) == 1
