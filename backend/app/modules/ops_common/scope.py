"""Who may see which section / student. Every Member 2 list endpoint filters through these helpers
in the database query itself (docs/INTEGRATION_GUIDE.md section 6, rule 4)."""
import uuid

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.ops_common.core_refs import (
    AcademicYear,
    Parent,
    Section,
    Student,
    StudentParent,
    Teacher,
    TeacherAssignment,
    User,
)


def not_found(what: str = "Record") -> AppError:
    return AppError(404, "not_found", f"{what} not found")


def get_or_404(db: Session, model, record_id: uuid.UUID, what: str):
    obj = db.get(model, record_id)
    if obj is None:
        raise not_found(what)
    return obj


def current_year_id(db: Session) -> uuid.UUID | None:
    return db.scalar(select(AcademicYear.id).where(AcademicYear.is_current.is_(True)))


def user_section_ids(user: User, db: Session) -> set[uuid.UUID] | None:
    """Sections the user may see. None means unrestricted (admin)."""
    if user.role == "admin":
        return None
    if user.role == "teacher":
        teacher_id = db.scalar(select(Teacher.id).where(Teacher.user_id == user.id))
        if teacher_id is None:
            return set()
        taught = set(db.scalars(select(TeacherAssignment.section_id).where(TeacherAssignment.teacher_id == teacher_id)))
        class_teacher = set(db.scalars(select(Section.id).where(Section.class_teacher_id == teacher_id)))
        return taught | class_teacher
    if user.role == "student":
        section_id = db.scalar(select(Student.section_id).where(Student.user_id == user.id, Student.is_active.is_(True)))
        return {section_id} if section_id else set()
    if user.role == "parent":
        stmt = (
            select(Student.section_id)
            .join(StudentParent, StudentParent.student_id == Student.id)
            .join(Parent, Parent.id == StudentParent.parent_id)
            .where(Parent.user_id == user.id, Student.is_active.is_(True))
        )
        return set(db.scalars(stmt))
    return set()


def user_class_ids(db: Session, section_ids: set[uuid.UUID]) -> set[uuid.UUID]:
    if not section_ids:
        return set()
    return set(db.scalars(select(Section.class_id).where(Section.id.in_(section_ids))))


def require_section_visible(user: User, db: Session, section_id: uuid.UUID, what: str = "Section") -> None:
    allowed = user_section_ids(user, db)
    if allowed is not None and section_id not in allowed:
        raise not_found(what)


def teacher_for_subject(db: Session, section_id: uuid.UUID, subject_id: uuid.UUID) -> uuid.UUID | None:
    """The teacher assigned to this subject in this section (current academic year preferred)."""
    year_id = current_year_id(db)
    stmt = select(TeacherAssignment.teacher_id).where(
        TeacherAssignment.section_id == section_id, TeacherAssignment.subject_id == subject_id
    )
    if year_id is not None:
        found = db.scalar(stmt.where(TeacherAssignment.academic_year_id == year_id))
        if found is not None:
            return found
    return db.scalar(stmt)


def student_section_id(db: Session, student_id: uuid.UUID) -> uuid.UUID | None:
    return db.scalar(select(Student.section_id).where(Student.id == student_id))


def audience_condition(model, user: User, db: Session):
    """SQL condition limiting an Event/Announcement query to what this user's audience allows.
    Returns None for admin (no restriction)."""
    if user.role == "admin":
        return None
    role_audience = {"teacher": "teachers", "student": "students", "parent": "parents"}.get(user.role)
    if role_audience is None:
        return model.audience == "__none__"
    conditions = [model.audience.in_(["all", role_audience])]
    sections = user_section_ids(user, db) or set()
    if sections:
        conditions.append(and_(model.audience == "class", model.section_id.in_(sections)))
        if hasattr(model, "class_id"):
            classes = user_class_ids(db, sections)
            conditions.append(
                and_(model.audience == "class", model.section_id.is_(None), model.class_id.in_(classes))
            )
    return or_(*conditions)
