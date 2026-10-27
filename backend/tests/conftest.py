"""Shared pytest fixtures.

TEMPORARY STUB written by Member 2 (Matee). Owner of the shared test setup is Member 1 (Faizan):
he may replace this file with his own. Member 2 only APPENDS fixtures to it and keeps every fixture
name below working. If he replaces it, keep: client, db, h, world, add_teacher, notes, PASSWORD.

The test school ("world"):
    Class 8 -> sections A and B;   Class 9 -> section 9-A (empty)
    subjects English, Mathematics, Science
    admin                      w.admin
    teacher users / rows       w.tu_a / w.t_a  (teaches English + Maths in section A)
                               w.tu_b / w.t_b  (teaches nothing)
    students (rows / users)    w.st_a1 / w.su_a1,  w.st_a2 / w.su_a2  (section A),  w.st_b1 / w.su_b1  (section B)
    parents (users / rows)     w.pu_a / w.p_a  (child: A1 only),  w.pu_b / w.p_b  (child: B1 only)
"""
from tests import _env  # noqa: F401  (must stay the first import)

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

import app.db_models  # noqa: F401  (registers every model on Base.metadata)
from app.core.database import Base, SessionLocal, engine
from app.core.security import create_access_token, hash_password
from app.main import app as fastapi_app
from app.modules.notifications.models import Notification
from app.modules.ops_common.core_refs import (
    AcademicYear, Parent, SchoolClass, Section, Student, StudentParent, Subject, Teacher, TeacherAssignment, User,
)

PASSWORD = "TestPass#123"
IS_SQLITE = engine.dialect.name == "sqlite"
BACKEND_DIR = Path(__file__).resolve().parents[1]
_hash_cache: list[str] = []


def _pw_hash() -> str:
    """bcrypt is slow on purpose, so hash once and give every test user the same hash."""
    if not _hash_cache:
        _hash_cache.append(hash_password(PASSWORD))
    return _hash_cache[0]


@pytest.fixture(scope="session", autouse=True)
def _schema():
    if not IS_SQLITE:
        # PostgreSQL: build the schema through the Alembic migrations (this also exercises them).
        from alembic import command
        from alembic.config import Config

        Base.metadata.drop_all(engine)
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
        command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _clean_db():
    """Every test starts with empty tables."""
    if IS_SQLITE:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
    else:
        names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    return TestClient(fastapi_app)


def auth_header(user: User) -> dict:
    return {"Authorization": "Bearer " + create_access_token(user.id, user.role)}


@pytest.fixture
def h():
    """h(user) -> {"Authorization": "Bearer ..."} without going through /auth/login."""
    return auth_header


def make_user(db, login_id: str, role: str, full_name: str) -> User:
    user = User(
        login_id=login_id, email=f"{login_id}@school.test", password_hash=_pw_hash(), role=role,
        full_name=full_name, is_active=True,
    )
    db.add(user)
    return user


@dataclass
class World:
    year: AcademicYear
    class_8: SchoolClass
    class_9: SchoolClass
    section_a: Section
    section_b: Section
    section_9a: Section
    english: Subject
    maths: Subject
    science: Subject
    admin: User
    tu_a: User
    tu_b: User
    t_a: Teacher
    t_b: Teacher
    su_a1: User
    su_a2: User
    su_b1: User
    st_a1: Student
    st_a2: Student
    st_b1: Student
    pu_a: User
    pu_b: User
    p_a: Parent
    p_b: Parent


def build_world(db) -> World:
    year = AcademicYear(name="2026-2027", start_date=date(2026, 4, 1), end_date=date(2027, 3, 31), is_current=True)
    class_8 = SchoolClass(name="Class 8", grade_level=8)
    class_9 = SchoolClass(name="Class 9", grade_level=9)
    english = Subject(name="English", code="ENG")
    maths = Subject(name="Mathematics", code="MAT")
    science = Subject(name="Science", code="SCI")
    db.add_all([year, class_8, class_9, english, maths, science])
    db.flush()
    section_a = Section(class_id=class_8.id, name="A")
    section_b = Section(class_id=class_8.id, name="B")
    section_9a = Section(class_id=class_9.id, name="A")
    admin = make_user(db, "admin", "admin", "School Admin")
    tu_a = make_user(db, "t.ahmed", "teacher", "Ahmed Khan")
    tu_b = make_user(db, "t.fatima", "teacher", "Fatima Noor")
    su_a1 = make_user(db, "s.a1", "student", "Ali Raza")
    su_a2 = make_user(db, "s.a2", "student", "Sara Malik")
    su_b1 = make_user(db, "s.b1", "student", "Bilal Shah")
    pu_a = make_user(db, "p.a", "parent", "Parent of A1")
    pu_b = make_user(db, "p.b", "parent", "Parent of B1")
    db.add_all([section_a, section_b, section_9a])
    db.flush()
    t_a = Teacher(user_id=tu_a.id, employee_no="T-001")
    t_b = Teacher(user_id=tu_b.id, employee_no="T-002")
    st_a1 = Student(user_id=su_a1.id, roll_no="A-01", full_name="Ali Raza", section_id=section_a.id)
    st_a2 = Student(user_id=su_a2.id, roll_no="A-02", full_name="Sara Malik", section_id=section_a.id)
    st_b1 = Student(user_id=su_b1.id, roll_no="B-01", full_name="Bilal Shah", section_id=section_b.id)
    p_a = Parent(user_id=pu_a.id)
    p_b = Parent(user_id=pu_b.id)
    db.add_all([t_a, t_b, st_a1, st_a2, st_b1, p_a, p_b])
    db.flush()
    db.add_all(
        [
            StudentParent(student_id=st_a1.id, parent_id=p_a.id, relation="father"),
            StudentParent(student_id=st_b1.id, parent_id=p_b.id, relation="mother"),
            TeacherAssignment(teacher_id=t_a.id, section_id=section_a.id, subject_id=english.id, academic_year_id=year.id),
            TeacherAssignment(teacher_id=t_a.id, section_id=section_a.id, subject_id=maths.id, academic_year_id=year.id),
        ]
    )
    db.commit()
    return World(
        year=year, class_8=class_8, class_9=class_9, section_a=section_a, section_b=section_b, section_9a=section_9a,
        english=english, maths=maths, science=science, admin=admin, tu_a=tu_a, tu_b=tu_b, t_a=t_a, t_b=t_b,
        su_a1=su_a1, su_a2=su_a2, su_b1=su_b1, st_a1=st_a1, st_a2=st_a2, st_b1=st_b1, pu_a=pu_a, pu_b=pu_b,
        p_a=p_a, p_b=p_b,
    )


@pytest.fixture
def world(db) -> World:
    return build_world(db)


@pytest.fixture
def add_teacher(db, world):
    """add_teacher("t.new", [(section, subject), ...]) -> (user, teacher)"""

    def _add(login_id: str, assignments=()):
        user = make_user(db, login_id, "teacher", login_id.title())
        db.flush()
        teacher = Teacher(user_id=user.id, employee_no=f"T-{login_id}")
        db.add(teacher)
        db.flush()
        for section, subject in assignments:
            db.add(
                TeacherAssignment(
                    teacher_id=teacher.id, section_id=section.id, subject_id=subject.id, academic_year_id=world.year.id
                )
            )
        db.commit()
        return user, teacher

    return _add


@pytest.fixture
def notes(db):
    """notes(user, type=None) -> that user's Notification rows, read fresh from the database."""

    def _notes(user: User, type: str | None = None) -> list[Notification]:
        stmt = select(Notification).where(Notification.user_id == user.id).execution_options(populate_existing=True)
        if type is not None:
            stmt = stmt.where(Notification.type == type)
        return list(db.scalars(stmt))

    return _notes


def assert_validation_error(response, field: str | None = None) -> None:
    """The 422 body shape promised by docs/API_CONTRACT.md section 1."""
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["errors"], body
    if field is not None:
        assert any(e["field"] == field for e in body["errors"]), body
