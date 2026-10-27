"""Module: School Calendar & Events."""
from datetime import date

from tests.conftest import assert_validation_error
from tests.ops.helpers import day, ids

URL = "/api/v1/events"


def event(**overrides):
    body = {"title": "Sports Day", "event_type": "sports", "start_date": day(10), "audience": "all"}
    body.update(overrides)
    return body


def test_admin_creates_event_and_everyone_is_notified(client, world, h, notes):
    r = client.post(URL, json=event(), headers=h(world.admin))
    assert r.status_code == 201
    assert r.json()["end_date"] == day(10)  # defaults to the start date
    for user in (world.tu_a, world.tu_b, world.su_a1, world.su_b1, world.pu_a, world.pu_b):
        assert len(notes(user, "event")) == 1


def test_event_can_be_created_silently(client, world, h, notes):
    assert client.post(URL, json=event(notify=False), headers=h(world.admin)).status_code == 201
    assert notes(world.su_a1) == []


def test_only_admin_changes_events(client, world, h):
    created = client.post(URL, json=event(), headers=h(world.admin)).json()
    for who in (world.tu_a, world.su_a1, world.pu_a):
        headers = h(who)
        assert client.post(URL, json=event(), headers=headers).status_code == 403
        assert client.patch(f"{URL}/{created['id']}", json={"title": "Hacked title"}, headers=headers).status_code == 403
        assert client.delete(f"{URL}/{created['id']}", headers=headers).status_code == 403


def test_event_validation(client, world, h):
    admin = h(world.admin)
    assert_validation_error(client.post(URL, json=event(start_date=day(5), end_date=day(2)), headers=admin))
    assert_validation_error(client.post(URL, json=event(start_time="12:00", end_time="11:00"), headers=admin))
    assert_validation_error(client.post(URL, json=event(audience="class"), headers=admin))  # needs a section
    assert_validation_error(client.post(URL, json=event(section_id=str(world.section_a.id)), headers=admin))
    assert_validation_error(client.post(URL, json=event(event_type="party"), headers=admin), "event_type")


def test_unknown_section_is_404(client, world, h):
    import uuid

    r = client.post(URL, json=event(audience="class", section_id=str(uuid.uuid4())), headers=h(world.admin))
    assert r.status_code == 404


def test_class_events_are_visible_only_to_that_section(client, world, h, notes):
    body = event(title="Class A trip", audience="class", section_id=str(world.section_a.id))
    created = client.post(URL, json=body, headers=h(world.admin)).json()
    for who in (world.su_a1, world.pu_a, world.tu_a, world.admin):  # section A, its parent, its teacher
        assert ids(client.get(URL, headers=h(who)).json()["items"]) == {created["id"]}, who.full_name
        assert client.get(f"{URL}/{created['id']}", headers=h(who)).status_code == 200
    for who in (world.su_b1, world.pu_b, world.tu_b):
        assert client.get(URL, headers=h(who)).json()["items"] == [], who.full_name
        assert client.get(f"{URL}/{created['id']}", headers=h(who)).status_code == 404
    assert len(notes(world.su_a1, "event")) == 1 and notes(world.su_b1, "event") == []


def test_role_audiences(client, world, h):
    teachers = client.post(URL, json=event(title="Staff meeting", event_type="meeting", audience="teachers"), headers=h(world.admin)).json()
    parents = client.post(URL, json=event(title="PTM day", event_type="meeting", audience="parents"), headers=h(world.admin)).json()
    assert ids(client.get(URL, headers=h(world.tu_a)).json()["items"]) == {teachers["id"]}
    assert ids(client.get(URL, headers=h(world.pu_a)).json()["items"]) == {parents["id"]}
    assert client.get(URL, headers=h(world.su_a1)).json()["items"] == []
    assert ids(client.get(URL, headers=h(world.admin)).json()["items"]) == {teachers["id"], parents["id"]}


def test_month_filter_and_overlap(client, world, h):
    admin = h(world.admin)
    this_month = date.today().replace(day=15)
    next_month = date(this_month.year + (this_month.month == 12), this_month.month % 12 + 1, 10)
    inside = client.post(URL, json=event(title="Mid-month", start_date=this_month.isoformat()), headers=admin).json()
    later = client.post(URL, json=event(title="Next month", start_date=next_month.isoformat()), headers=admin).json()
    got = client.get(URL, params={"month": f"{this_month:%Y-%m}"}, headers=admin).json()
    assert ids(got["items"]) == {inside["id"]}
    assert later["id"] in ids(client.get(URL, params={"month": f"{next_month:%Y-%m}"}, headers=admin).json()["items"])
    # a long event spanning the whole month overlaps it even though it starts earlier
    span = client.post(
        URL, json=event(title="Winter break", event_type="holiday", start_date=day(-60), end_date=day(60)), headers=admin
    ).json()
    assert span["id"] in ids(client.get(URL, params={"month": f"{this_month:%Y-%m}"}, headers=admin).json()["items"])


def test_bad_month_and_type_filters(client, world, h):
    admin = h(world.admin)
    assert client.get(URL, params={"month": "2026-13"}, headers=admin).status_code == 422
    assert client.get(URL, params={"month": "October"}, headers=admin).status_code == 422
    client.post(URL, json=event(), headers=admin)
    client.post(URL, json=event(title="Eid holiday", event_type="holiday"), headers=admin)
    assert client.get(URL, params={"event_type": "holiday"}, headers=admin).json()["total"] == 1


def test_update_and_delete(client, world, h):
    admin = h(world.admin)
    created = client.post(URL, json=event(), headers=admin).json()
    r = client.patch(f"{URL}/{created['id']}", json={"title": "Annual Sports Day", "location": "School ground"}, headers=admin)
    assert r.status_code == 200 and r.json()["location"] == "School ground"
    assert client.patch(f"{URL}/{created['id']}", json={"end_date": day(1)}, headers=admin).status_code == 422
    assert client.delete(f"{URL}/{created['id']}", headers=admin).status_code == 204
    assert client.get(f"{URL}/{created['id']}", headers=admin).status_code == 404
