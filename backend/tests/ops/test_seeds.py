"""The seed scripts are idempotent and produce a school the API can actually use."""
from sqlalchemy import func, select

from seeds import seed_core, seed_ops
from app.modules.announcements.models import Announcement
from app.modules.exams.models import GradeScale
from app.modules.fees.models import FeeStructure
from app.modules.timetable.models import TimetableSlot
from tests.conftest import PASSWORD


def _counts(db):
    return {
        "grades": db.scalar(select(func.count()).select_from(GradeScale)),
        "fees": db.scalar(select(func.count()).select_from(FeeStructure)),
        "slots": db.scalar(select(func.count()).select_from(TimetableSlot)),
        "announcements": db.scalar(select(func.count()).select_from(Announcement)),
    }


def test_seeding_twice_creates_no_duplicates(db):
    first_core = seed_core.run(db)
    first_ops = seed_ops.run(db)
    db.commit()
    assert first_core["users"] == 7 and first_core["classes"] == 10
    assert first_ops["grade_scales"] == 7 and first_ops["fee_structures"] == 40 and first_ops["timetable_slots"] == 25
    before = _counts(db)

    assert seed_core.run(db) == {}
    assert seed_ops.run(db) == {}
    assert _counts(db) == before


def test_seed_ops_needs_the_foundation_first(db):
    import pytest

    with pytest.raises(RuntimeError):
        seed_ops.run(db)


def test_seeded_accounts_can_log_in_and_see_the_sample_timetable(client, db):
    seed_core.run(db)
    seed_ops.run(db)
    db.commit()

    def login(login_id, platform):
        r = client.post("/api/v1/auth/login", json={"login_id": login_id, "password": PASSWORD}, headers={"X-Client-Platform": platform})
        assert r.status_code == 200, r.text
        return {"Authorization": "Bearer " + r.json()["access_token"]}

    student = client.get("/api/v1/timetable/me", headers=login("s.ali", "mobile")).json()
    assert len(student["slots"]) == 25
    parent_fees = client.get("/api/v1/fee-invoices", headers=login("p.ali", "mobile"))
    assert parent_fees.status_code == 200 and parent_fees.json()["items"] == []
    teacher = client.get("/api/v1/lookups/my-teaching", headers=login("t.ahmed", "web")).json()
    assert {t["subject_name"] for t in teacher} == {"English", "Mathematics"}
    # the sample grade scale is complete
    assert len(client.get("/api/v1/grade-scales", headers=login("admin", "web")).json()) == 7
