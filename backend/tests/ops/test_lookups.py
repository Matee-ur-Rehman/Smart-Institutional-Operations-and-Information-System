"""Read-only helper lists used by the Flutter dropdowns (docs/API_CONTRACT.md section 7)."""
from tests.ops.helpers import ids

BASE = "/api/v1/lookups"


def test_current_academic_year(client, world, h):
    r = client.get(f"{BASE}/academic-year/current", headers=h(world.su_a1))
    assert r.status_code == 200 and r.json()["name"] == "2026-2027"


def test_no_current_year_is_404(client, db, world, h):
    world.year.is_current = False
    db.commit()
    assert client.get(f"{BASE}/academic-year/current", headers=h(world.admin)).status_code == 404


def test_sections_are_scoped_to_the_caller(client, world, h):
    def displays(user):
        return [s["display"] for s in client.get(f"{BASE}/sections", headers=h(user)).json()]

    assert displays(world.admin) == ["Class 8-A", "Class 8-B", "Class 9-A"]
    assert displays(world.tu_a) == ["Class 8-A"]
    assert displays(world.tu_b) == []
    assert displays(world.su_a1) == ["Class 8-A"]
    assert displays(world.pu_b) == ["Class 8-B"]


def test_classes_are_scoped_to_the_caller(client, world, h):
    assert len(client.get(f"{BASE}/classes", headers=h(world.admin)).json()) == 2
    assert [c["name"] for c in client.get(f"{BASE}/classes", headers=h(world.su_a1)).json()] == ["Class 8"]


def test_subjects_for_everyone(client, world, h):
    assert len(client.get(f"{BASE}/subjects", headers=h(world.pu_a)).json()) == 3


def test_teacher_lists_only_students_of_their_sections(client, world, h):
    mine = client.get(f"{BASE}/students", params={"section_id": str(world.section_a.id)}, headers=h(world.tu_a)).json()
    assert [s["roll_no"] for s in mine] == ["A-01", "A-02"]
    assert client.get(f"{BASE}/students", params={"section_id": str(world.section_b.id)}, headers=h(world.tu_a)).status_code == 404
    everything = client.get(f"{BASE}/students", headers=h(world.tu_a)).json()
    assert {s["roll_no"] for s in everything} == {"A-01", "A-02"}
    assert client.get(f"{BASE}/students", headers=h(world.tu_b)).json() == []
    assert len(client.get(f"{BASE}/students", headers=h(world.admin)).json()) == 3


def test_parent_sees_only_their_own_children(client, world, h):
    kids = client.get(f"{BASE}/my-children", headers=h(world.pu_a)).json()
    assert [k["id"] for k in kids] == [str(world.st_a1.id)]
    assert [k["id"] for k in client.get(f"{BASE}/my-children", headers=h(world.pu_b)).json()] == [str(world.st_b1.id)]
    assert client.get(f"{BASE}/my-children", headers=h(world.su_a1)).status_code == 403


def test_my_teaching_and_my_student(client, world, h):
    teaching = client.get(f"{BASE}/my-teaching", headers=h(world.tu_a)).json()
    assert {t["subject_name"] for t in teaching} == {"English", "Mathematics"}
    assert client.get(f"{BASE}/my-teaching", headers=h(world.tu_b)).json() == []
    assert client.get(f"{BASE}/my-teaching", headers=h(world.su_a1)).status_code == 403
    me = client.get(f"{BASE}/my-student", headers=h(world.su_a1)).json()
    assert me["id"] == str(world.st_a1.id)
    assert client.get(f"{BASE}/my-student", headers=h(world.pu_a)).status_code == 403


def test_admin_lists_teachers(client, world, h):
    assert ids([{"id": t["id"]} for t in client.get(f"{BASE}/teachers", headers=h(world.admin)).json()]) == {
        str(world.t_a.id), str(world.t_b.id)
    }
