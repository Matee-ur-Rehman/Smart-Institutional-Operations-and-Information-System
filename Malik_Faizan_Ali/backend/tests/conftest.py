"""
Shared test fixtures (INTEGRATION_GUIDE section 8).

* Runs ONLY against the test database (TEST_DATABASE_URL). The schema is created once per session by running
  the Alembic migrations, so the migrations themselves are tested.
* The app commits inside endpoints, so isolation is done by TRUNCATE between tests (one statement).
* `world` builds a small school (2 sections, teachers, students, parents); `api` is a thin client wrapper.
"""
import os
import tempfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

# --- must happen before anything imports app.core.database (it builds the engine on import) -------------------
from app.core.config import settings  # noqa: E402

settings.DATABASE_URL = settings.TEST_DATABASE_URL
if "test" not in settings.DATABASE_URL.rsplit("/", 1)[-1]:
    raise RuntimeError("Refusing to run tests: TEST_DATABASE_URL must point at a database whose name contains 'test'")
settings.UPLOAD_DIR = tempfile.mkdtemp(prefix="siois_uploads_")
settings.FCM_ENABLED = False
settings.JWT_SECRET_KEY = "test-secret-key-for-pytest-only-0123456789abcdef"
os.environ["ALEMBIC_DATABASE_URL"] = settings.TEST_DATABASE_URL

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.common.timeutil import school_today  # noqa: E402
from app.core.database import SessionLocal, engine  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.exams.models import GradeScale  # noqa: E402
from app.modules.foundation.models import (  # noqa: E402
    AcademicYear, Parent, SchoolClass, Section, Student, StudentParent, Subject, Teacher, TeacherAssignment, User,
)

BACKEND = Path(__file__).resolve().parents[1]
PASSWORD = "Pass@1234"
_HASH = hash_password(PASSWORD)  # hashed once: bcrypt is deliberately slow
API = "/api/v1"


@pytest.fixture(scope="session", autouse=True)
def _schema():
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    command.upgrade(cfg, "head")
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean(_schema):
    with engine.begin() as conn:
        names = [r[0] for r in conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename <> 'alembic_version'"))]
        conn.execute(text("TRUNCATE " + ", ".join(f'"{n}"' for n in names) + " RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture(scope="session")
def client():
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


def bearer(user) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}


class Api:
    """`api.get('/assignments', user)` -> Response. user=None sends no token."""

    def __init__(self, client: TestClient):
        self.c = client

    def _go(self, method, path, user=None, headers=None, **kw):
        h = dict(bearer(user)) if user is not None else {}
        h.update(headers or {})
        return self.c.request(method, API + path, headers=h, **kw)

    def get(self, path, user=None, **kw):
        return self._go("GET", path, user, **kw)

    def post(self, path, user=None, **kw):
        return self._go("POST", path, user, **kw)

    def put(self, path, user=None, **kw):
        return self._go("PUT", path, user, **kw)

    def patch(self, path, user=None, **kw):
        return self._go("PATCH", path, user, **kw)

    def delete(self, path, user=None, **kw):
        return self._go("DELETE", path, user, **kw)


@pytest.fixture
def api(client):
    return Api(client)


def _user(db, login, role, name):
    u = User(login_id=login, email=f"{login}@example.test", password_hash=_HASH, role=role, full_name=name,
             phone="0300-0000000")
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def world(db):
    """
    admin; teacher_a (8-A Math + English), teacher_b (8-B Math), teacher_c (no classes);
    8-A: a1,a2,a3   8-B: b1,b2   9-A: c1 (a different class, for class-targeted records);
    parent_1 -> a1 + b1 (children in different sections), parent_2 -> b2.  a2, a3, c1 have no parent.
    Grade scale is installed (A+ .. F, F fails).
    """
    today = school_today()
    w = SimpleNamespace(today=today, password=PASSWORD)
    w.year = AcademicYear(name="2026-2027", start_date=today - timedelta(days=100), end_date=today + timedelta(days=250),
                          is_current=True)
    db.add(w.year)
    w.class8, w.class9 = SchoolClass(name="Class 8", grade_level=8), SchoolClass(name="Class 9", grade_level=9)
    db.add_all([w.class8, w.class9])
    db.flush()
    w.sec_a, w.sec_b = Section(class_id=w.class8.id, name="A"), Section(class_id=w.class8.id, name="B")
    w.sec_9a = Section(class_id=w.class9.id, name="A")
    db.add_all([w.sec_a, w.sec_b, w.sec_9a])
    w.math, w.english, w.science = (Subject(name="Mathematics", code="MATH"), Subject(name="English", code="ENG"),
                                    Subject(name="Science", code="SCI"))
    db.add_all([w.math, w.english, w.science])

    w.admin = _user(db, "admin", "admin", "Admin User")
    w.ua, w.ub, w.uc = (_user(db, "t.a", "teacher", "Teacher A"), _user(db, "t.b", "teacher", "Teacher B"),
                        _user(db, "t.c", "teacher", "Teacher C"))
    db.flush()
    w.teacher_a, w.teacher_b, w.teacher_c = (Teacher(user_id=w.ua.id, employee_no="E1"), Teacher(user_id=w.ub.id, employee_no="E2"),
                                             Teacher(user_id=w.uc.id, employee_no="E3"))
    db.add_all([w.teacher_a, w.teacher_b, w.teacher_c])
    db.flush()
    for t, sec, sub in ((w.teacher_a, w.sec_a, w.math), (w.teacher_a, w.sec_a, w.english), (w.teacher_b, w.sec_b, w.math)):
        db.add(TeacherAssignment(teacher_id=t.id, section_id=sec.id, subject_id=sub.id, academic_year_id=w.year.id))

    def student(key, name, sec):
        u = _user(db, f"s.{key}", "student", name)
        st = Student(user_id=u.id, roll_no=key.upper(), full_name=name, section_id=sec.id)
        db.add(st)
        db.flush()
        setattr(w, f"user_{key}", u)
        setattr(w, key, st)

    student("a1", "Ali Ahmed", w.sec_a)
    student("a2", "Bilal Khan", w.sec_a)
    student("a3", "Chand Bibi", w.sec_a)
    student("b1", "Danish Raza", w.sec_b)
    student("b2", "Esha Noor", w.sec_b)
    student("c1", "Fahad Ali", w.sec_9a)

    w.up1, w.up2 = _user(db, "p.1", "parent", "Parent One"), _user(db, "p.2", "parent", "Parent Two")
    w.parent_1, w.parent_2 = Parent(user_id=w.up1.id), Parent(user_id=w.up2.id)
    db.add_all([w.parent_1, w.parent_2])
    db.flush()
    for p, s in ((w.parent_1, w.a1), (w.parent_1, w.b1), (w.parent_2, w.b2)):
        db.add(StudentParent(student_id=s.id, parent_id=p.id, relation="father"))
    for g, lo, hi, gpa, ok in (("A+", 90, 100, 4.0, True), ("A", 80, 89.99, 3.7, True), ("B", 70, 79.99, 3.0, True),
                               ("C", 60, 69.99, 2.0, True), ("D", 50, 59.99, 1.0, True), ("E", 40, 49.99, 0.5, True),
                               ("F", 0, 39.99, 0.0, False)):
        db.add(GradeScale(grade=g, min_percentage=Decimal(str(lo)), max_percentage=Decimal(str(hi)),
                          gpa_points=Decimal(str(gpa)), remark=g, is_pass=ok))
    db.commit()
    # friendly aliases
    w.teacher_user_a, w.teacher_user_b, w.teacher_user_c = w.ua, w.ub, w.uc
    return w


def D(v) -> Decimal:
    return Decimal(str(v))


# ------------------------------------------------------------------ scenario helpers used by several modules
@pytest.fixture
def make_exam(api, world):
    """make_exam(status='scheduled') -> (exam_json, {'math': sched_json, 'eng': sched_json}) for section 8-A."""

    def _make(status="scheduled", name="Midterm 2026", with_papers=True):
        w = world
        r = api.post("/exams", w.admin, json={"name": name, "exam_type": "midterm", "start_date": str(w.today),
                                              "end_date": str(w.today + timedelta(days=7)), "status": status})
        assert r.status_code == 201, r.text
        exam = r.json()
        papers = {}
        if with_papers:
            for key, sub, h in (("math", w.math, 9), ("eng", w.english, 12)):
                r = api.post(f"/exams/{exam['id']}/schedules", w.admin, json={
                    "section_id": str(w.sec_a.id), "subject_id": str(sub.id), "exam_date": str(w.today + timedelta(days=1)),
                    "start_time": f"{h:02d}:00", "end_time": f"{h + 2:02d}:00", "room": "R1", "total_marks": 100, "passing_marks": 33})
                assert r.status_code == 201, r.text
                papers[key] = r.json()
        return exam, papers

    return _make


def entries(*rows):
    """entries((student, marks_or_None, absent?), ...) -> PUT body."""
    out = []
    for r in rows:
        st, marks = r[0], r[1]
        out.append({"student_id": str(st.id), "marks_obtained": marks, "is_absent": bool(len(r) > 2 and r[2])})
    return {"entries": out}
