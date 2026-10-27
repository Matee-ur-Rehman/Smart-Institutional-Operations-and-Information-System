"""Demo data for the SHARED foundation tables (docs/DATABASE_SCHEMA.md section 2).

TEMPORARY STUB written by Member 2 (Matee) so his seed and tests have people, classes and subjects to
work with before Faizan's code is merged. Owner: Member 1 (Faizan): replace this file with his
`seed_core.py`; `seed_ops.py` only needs these tables to be filled (users, classes, sections,
subjects, a current academic year, teachers, students, parents and teacher_assignments).

Run from backend/:   python -m seeds.seed_core
Safe to run twice (nothing is duplicated). DEMO ACCOUNTS ONLY: never run it on a real school database.
All demo accounts get the password in SEED_DEFAULT_PASSWORD (backend/.env).
"""
import sys
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.modules.ops_common.core_refs import (
    AcademicYear, Parent, SchoolClass, Section, Student, StudentParent, Subject, Teacher, TeacherAssignment, User,
)

# Default school layout. Change freely: these are only starting values.
CLASS_COUNT = 10  # Class 1 ... Class 10
SUBJECTS = [
    ("English", "ENG"), ("Urdu", "URD"), ("Mathematics", "MAT"), ("Science", "SCI"),
    ("Islamiat", "ISL"), ("Social Studies", "SST"), ("Computer Science", "CS"),
]


def _one(db: Session, model, **lookup):
    return db.scalar(select(model).filter_by(**lookup))


def _get_or_create(db: Session, model, created: dict, key: str, defaults: dict | None = None, **lookup):
    obj = _one(db, model, **lookup)
    if obj is None:
        obj = model(**lookup, **(defaults or {}))
        db.add(obj)
        db.flush()
        created[key] = created.get(key, 0) + 1
    return obj


def run(db: Session) -> dict:
    """Create the demo foundation data. Flushes but does not commit: the caller commits."""
    if not settings.seed_default_password:
        raise RuntimeError("Set SEED_DEFAULT_PASSWORD in backend/.env before seeding demo accounts")
    password_hash = hash_password(settings.seed_default_password)
    created: dict = {}

    today = date.today()
    start_year = today.year if today.month >= 4 else today.year - 1
    year = _get_or_create(
        db, AcademicYear, created, "academic_years", name=f"{start_year}-{start_year + 1}",
        defaults={"start_date": date(start_year, 4, 1), "end_date": date(start_year + 1, 3, 31)},
    )
    if _one(db, AcademicYear, is_current=True) is None:
        year.is_current = True

    classes = {}
    for grade in range(1, CLASS_COUNT + 1):
        classes[grade] = _get_or_create(db, SchoolClass, created, "classes", name=f"Class {grade}", defaults={"grade_level": grade})
    sections = {g: _get_or_create(db, Section, created, "sections", class_id=c.id, name="A") for g, c in classes.items()}
    subjects = {code: _get_or_create(db, Subject, created, "subjects", code=code, defaults={"name": name}) for name, code in SUBJECTS}

    def user(login_id: str, role: str, full_name: str) -> User:
        return _get_or_create(
            db, User, created, "users", login_id=login_id,
            defaults={"role": role, "full_name": full_name, "password_hash": password_hash, "email": f"{login_id}@trends.demo"},
        )

    user("admin", "admin", "School Administrator")

    teachers = {}
    for login_id, name, employee_no in [("t.ahmed", "Ahmed Khan", "T-001"), ("t.fatima", "Fatima Noor", "T-002")]:
        u = user(login_id, "teacher", name)
        teachers[login_id] = _get_or_create(db, Teacher, created, "teachers", user_id=u.id, defaults={"employee_no": employee_no})

    # Class 8-A: Ahmed teaches English + Mathematics, Fatima teaches Science + Urdu
    plan = [("t.ahmed", "ENG"), ("t.ahmed", "MAT"), ("t.fatima", "SCI"), ("t.fatima", "URD")]
    for login_id, code in plan:
        _get_or_create(
            db, TeacherAssignment, created, "teacher_assignments", section_id=sections[8].id, subject_id=subjects[code].id,
            academic_year_id=year.id, defaults={"teacher_id": teachers[login_id].id},
        )

    for s_login, s_name, roll_no, p_login, p_name in [
        ("s.ali", "Ali Raza", "8A-01", "p.ali", "Raza Ahmed"),
        ("s.sara", "Sara Malik", "8A-02", "p.sara", "Malik Tariq"),
    ]:
        s_user = user(s_login, "student", s_name)
        student = _get_or_create(
            db, Student, created, "students", roll_no=roll_no,
            defaults={"user_id": s_user.id, "full_name": s_name, "section_id": sections[8].id},
        )
        p_user = user(p_login, "parent", p_name)
        parent = _get_or_create(db, Parent, created, "parents", user_id=p_user.id)
        _get_or_create(db, StudentParent, created, "student_parents", student_id=student.id, parent_id=parent.id, defaults={"relation": "father"})

    db.flush()
    return created


def main() -> None:
    if settings.app_env.lower() == "production":
        sys.exit("Refusing to create demo accounts when APP_ENV=production")
    try:
        with SessionLocal() as db:
            result = run(db)
            db.commit()
    except RuntimeError as exc:
        sys.exit(str(exc))
    print("seed_core done. Created:", result or "nothing (already seeded)")


if __name__ == "__main__":
    main()
