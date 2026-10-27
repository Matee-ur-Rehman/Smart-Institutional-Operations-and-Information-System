"""Record-level ownership helpers (docs/API_CONTRACT.md section 2, "Shared dependencies").

TEMPORARY STUB written by Member 2. Owner: Member 1 (Faizan). Signatures are the agreed contract.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.stub_models import Parent, Student, StudentParent, Teacher, TeacherAssignment, User


def teacher_id_for(user: User, db: Session) -> uuid.UUID:
    teacher_id = db.scalar(select(Teacher.id).where(Teacher.user_id == user.id, Teacher.is_active.is_(True)))
    if teacher_id is None:
        raise AppError(403, "forbidden", "No active teacher profile for this account")
    return teacher_id


def teacher_teaches(db: Session, teacher_id: uuid.UUID, section_id: uuid.UUID, subject_id: uuid.UUID) -> bool:
    found = db.scalar(
        select(TeacherAssignment.id).where(
            TeacherAssignment.teacher_id == teacher_id,
            TeacherAssignment.section_id == section_id,
            TeacherAssignment.subject_id == subject_id,
        )
    )
    return found is not None


def student_id_for(user: User, db: Session) -> uuid.UUID:
    student_id = db.scalar(select(Student.id).where(Student.user_id == user.id, Student.is_active.is_(True)))
    if student_id is None:
        raise AppError(403, "forbidden", "No active student profile for this account")
    return student_id


def parent_child_ids(user: User, db: Session) -> list[uuid.UUID]:
    stmt = (
        select(Student.id)
        .join(StudentParent, StudentParent.student_id == Student.id)
        .join(Parent, Parent.id == StudentParent.parent_id)
        .where(Parent.user_id == user.id, Student.is_active.is_(True))
    )
    return list(db.scalars(stmt))


def can_access_student(user: User, student_id: uuid.UUID, db: Session) -> bool:
    if user.role == "admin":
        return True
    if user.role == "student":
        return db.scalar(select(Student.id).where(Student.id == student_id, Student.user_id == user.id)) is not None
    if user.role == "parent":
        return student_id in parent_child_ids(user, db)
    if user.role == "teacher":
        teacher_id = db.scalar(select(Teacher.id).where(Teacher.user_id == user.id))
        section_id = db.scalar(select(Student.section_id).where(Student.id == student_id))
        if teacher_id is None or section_id is None:
            return False
        return (
            db.scalar(
                select(TeacherAssignment.id).where(
                    TeacherAssignment.teacher_id == teacher_id, TeacherAssignment.section_id == section_id
                )
            )
            is not None
        )
    return False
