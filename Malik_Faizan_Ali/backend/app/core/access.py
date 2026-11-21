"""
Record-level access helpers (API_CONTRACT.md section 2). Member 1 owns this file; this is a
TEMPORARY STUB with the agreed signatures. Role checks alone are not enough for records.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Forbidden
from app.modules.foundation.models import (
    AcademicYear, Parent, Student, StudentParent, Teacher, TeacherAssignment,
)

_CURRENT_YEAR = select(AcademicYear.id).where(AcademicYear.is_current).scalar_subquery()


def teacher_id_for(user, db: Session) -> uuid.UUID:
    tid = db.scalar(select(Teacher.id).where(Teacher.user_id == user.id, Teacher.is_active))
    if tid is None:
        raise Forbidden("No active teacher profile for this account")
    return tid


def teacher_teaches(db: Session, teacher_id: uuid.UUID, section_id: uuid.UUID, subject_id: uuid.UUID) -> bool:
    return db.scalar(
        select(TeacherAssignment.id).where(
            TeacherAssignment.teacher_id == teacher_id,
            TeacherAssignment.section_id == section_id,
            TeacherAssignment.subject_id == subject_id,
            TeacherAssignment.academic_year_id == _CURRENT_YEAR,
        ).limit(1)
    ) is not None


def student_id_for(user, db: Session) -> uuid.UUID:
    sid = db.scalar(select(Student.id).where(Student.user_id == user.id, Student.is_active))
    if sid is None:
        raise Forbidden("No active student profile for this account")
    return sid


def parent_child_ids(user, db: Session) -> list[uuid.UUID]:
    return list(db.scalars(
        select(StudentParent.student_id)
        .join(Parent, Parent.id == StudentParent.parent_id)
        .join(Student, Student.id == StudentParent.student_id)
        .where(Parent.user_id == user.id, Student.is_active)
    ))


def can_access_student(user, student_id: uuid.UUID, db: Session) -> bool:
    """admin: any; teacher: teaches their section; student: self; parent: linked child."""
    if user.role == "admin":
        return True
    if user.role == "student":
        return db.scalar(select(Student.id).where(Student.id == student_id, Student.user_id == user.id)) is not None
    if user.role == "parent":
        return student_id in parent_child_ids(user, db)
    if user.role == "teacher":
        tid = db.scalar(select(Teacher.id).where(Teacher.user_id == user.id, Teacher.is_active))
        if tid is None:
            return False
        section_id = db.scalar(select(Student.section_id).where(Student.id == student_id))
        if section_id is None:
            return False
        return db.scalar(
            select(TeacherAssignment.id).where(
                TeacherAssignment.teacher_id == tid, TeacherAssignment.section_id == section_id,
                TeacherAssignment.academic_year_id == _CURRENT_YEAR,
            ).limit(1)
        ) is not None
    return False
