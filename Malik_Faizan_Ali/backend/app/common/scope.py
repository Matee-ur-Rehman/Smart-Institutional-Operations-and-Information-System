"""
Read-only scoping + label helpers used by the operations modules (Member 2).
They only READ Member 1's tables (allowed by DATABASE_SCHEMA.md "Ownership").
"""
import uuid
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.access import parent_child_ids
from app.core.errors import BadRequest, NotFound
from app.modules.foundation.models import (
    AcademicYear, Parent, SchoolClass, Section, Student, StudentParent, Subject, Teacher,
    TeacherAssignment, User,
)


def current_year(db: Session) -> AcademicYear:
    year = db.scalar(select(AcademicYear).where(AcademicYear.is_current))
    if year is None:
        raise BadRequest("No current academic year is configured", code="no_current_year")
    return year


def current_year_id(db: Session) -> uuid.UUID:
    return current_year(db).id


# ---------------------------------------------------------------- teacher scope
def teacher_pairs(db: Session, teacher_id: uuid.UUID) -> set[tuple[uuid.UUID, uuid.UUID]]:
    """(section_id, subject_id) pairs a teacher teaches in the current academic year."""
    rows = db.execute(
        select(TeacherAssignment.section_id, TeacherAssignment.subject_id).where(
            TeacherAssignment.teacher_id == teacher_id,
            TeacherAssignment.academic_year_id == current_year_id(db),
        )
    ).all()
    return {(r[0], r[1]) for r in rows}


def teacher_section_ids(db: Session, teacher_id: uuid.UUID) -> set[uuid.UUID]:
    return {s for s, _ in teacher_pairs(db, teacher_id)}


def teacher_teaches_section(db: Session, teacher_id: uuid.UUID, section_id: uuid.UUID) -> bool:
    return section_id in teacher_section_ids(db, teacher_id)


# ---------------------------------------------------------------- who can see which sections
def section_of_student(db: Session, student_id: uuid.UUID) -> uuid.UUID | None:
    return db.scalar(select(Student.section_id).where(Student.id == student_id))


def own_student(user, db: Session) -> Student | None:
    return db.scalar(select(Student).where(Student.user_id == user.id, Student.is_active))


def child_section_ids(user, db: Session) -> set[uuid.UUID]:
    ids = parent_child_ids(user, db)
    if not ids:
        return set()
    return set(db.scalars(select(Student.section_id).where(Student.id.in_(ids))))


def visible_section_ids(user, db: Session) -> set[uuid.UUID] | None:
    """Sections whose class-level records the caller may see. None = unrestricted (admin)."""
    if user.role == "admin":
        return None
    if user.role == "teacher":
        tid = db.scalar(select(Teacher.id).where(Teacher.user_id == user.id, Teacher.is_active))
        return teacher_section_ids(db, tid) if tid else set()
    if user.role == "student":
        st = own_student(user, db)
        return {st.section_id} if st else set()
    if user.role == "parent":
        return child_section_ids(user, db)
    return set()


def require_visible_section(user, db: Session, section_id: uuid.UUID) -> None:
    allowed = visible_section_ids(user, db)
    if allowed is not None and section_id not in allowed:
        raise NotFound("Section not found")


def linked_child(user, db: Session, student_id: uuid.UUID) -> Student:
    """A parent's linked child, or 404 (never reveals other families' children)."""
    if student_id not in parent_child_ids(user, db):
        raise NotFound("Student not found")
    return db.get(Student, student_id)


def audience_user_ids_for_section(db: Session, section_id: uuid.UUID, *, include_parents=True,
                                  include_students=True, include_teachers=False) -> list[uuid.UUID]:
    ids: set[uuid.UUID] = set()
    if include_students:
        ids.update(db.scalars(select(Student.user_id).where(
            Student.section_id == section_id, Student.is_active, Student.user_id.is_not(None))))
    if include_parents:
        ids.update(db.scalars(
            select(Parent.user_id)
            .join(StudentParent, StudentParent.parent_id == Parent.id)
            .join(Student, Student.id == StudentParent.student_id)
            .where(Student.section_id == section_id, Student.is_active)))
    if include_teachers:
        ids.update(db.scalars(
            select(Teacher.user_id).join(TeacherAssignment, TeacherAssignment.teacher_id == Teacher.id)
            .where(TeacherAssignment.section_id == section_id,
                   TeacherAssignment.academic_year_id == current_year_id(db), Teacher.is_active)))
    return [i for i in ids if i is not None]


def parent_user_ids_of_student(db: Session, student_id: uuid.UUID) -> list[uuid.UUID]:
    return list(db.scalars(
        select(Parent.user_id).join(StudentParent, StudentParent.parent_id == Parent.id)
        .where(StudentParent.student_id == student_id)))


def admin_user_ids(db: Session) -> list[uuid.UUID]:
    return list(db.scalars(select(User.id).where(User.role == "admin", User.is_active)))


# ---------------------------------------------------------------- labels (bulk lookups)
def section_labels(db: Session, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = db.execute(
        select(Section.id, SchoolClass.name, Section.name)
        .join(SchoolClass, SchoolClass.id == Section.class_id).where(Section.id.in_(ids))
    ).all()
    return {r[0]: f"{r[1]}-{r[2]}" for r in rows}


def section_class_ids(db: Session, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, uuid.UUID]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {r[0]: r[1] for r in db.execute(select(Section.id, Section.class_id).where(Section.id.in_(ids))).all()}


def subject_names(db: Session, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {r[0]: r[1] for r in db.execute(select(Subject.id, Subject.name).where(Subject.id.in_(ids))).all()}


def teacher_names(db: Session, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = db.execute(
        select(Teacher.id, User.full_name).join(User, User.id == Teacher.user_id).where(Teacher.id.in_(ids))
    ).all()
    return {r[0]: r[1] for r in rows}


def user_names(db: Session, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, str]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {r[0]: r[1] for r in db.execute(select(User.id, User.full_name).where(User.id.in_(ids))).all()}


def student_labels(db: Session, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, dict]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    rows = db.execute(select(Student.id, Student.full_name, Student.roll_no, Student.section_id)
                      .where(Student.id.in_(ids))).all()
    secs = section_labels(db, [r[3] for r in rows])
    return {r[0]: {"student_id": r[0], "full_name": r[1], "roll_no": r[2], "section_id": r[3],
                   "section_label": secs.get(r[3])} for r in rows}
