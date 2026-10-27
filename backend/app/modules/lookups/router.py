"""Read-only helper lists for the Flutter screens (dropdowns: classes, sections, subjects, my children ...).

These are Member 2's convenience endpoints. Member 1's real CRUD endpoints for the same entities are
separate and unaffected (docs/API_CONTRACT.md section 7). Everything is scoped in the SQL query with
the same helpers the other Member 2 modules use (app.modules.ops_common.scope).
"""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.access import student_id_for, teacher_id_for
from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import get_current_user, require_roles
from app.modules.ops_common.core_refs import (
    AcademicYear, Parent, SchoolClass, Section, Student, StudentParent, Subject, Teacher, TeacherAssignment, User,
)
from app.modules.ops_common.scope import (
    current_year_id, not_found, require_section_visible, user_class_ids, user_section_ids,
)

router = APIRouter(prefix="/lookups", tags=["Lookups (read-only)"])


class YearOut(BaseModel):
    id: uuid.UUID
    name: str
    start_date: date
    end_date: date


class ClassOut(BaseModel):
    id: uuid.UUID
    name: str
    grade_level: int


class SectionOut(BaseModel):
    id: uuid.UUID
    name: str
    class_id: uuid.UUID
    class_name: str
    display: str  # e.g. "Class 8-A"


class SubjectOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str


class TeacherOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    full_name: str
    employee_no: str


class StudentOut(BaseModel):
    id: uuid.UUID
    roll_no: str
    full_name: str
    section_id: uuid.UUID
    section_name: str


class TeachingOut(BaseModel):
    section_id: uuid.UUID
    section_name: str
    subject_id: uuid.UUID
    subject_name: str


def _section_out(row) -> SectionOut:
    section, class_name = row
    return SectionOut(
        id=section.id, name=section.name, class_id=section.class_id, class_name=class_name,
        display=f"{class_name}-{section.name}",
    )


def _student_out(row) -> StudentOut:
    student, class_name, section_name = row
    return StudentOut(
        id=student.id, roll_no=student.roll_no, full_name=student.full_name, section_id=student.section_id,
        section_name=f"{class_name}-{section_name}",
    )


def _student_query():
    return (
        select(Student, SchoolClass.name, Section.name)
        .join(Section, Section.id == Student.section_id)
        .join(SchoolClass, SchoolClass.id == Section.class_id)
        .where(Student.is_active.is_(True))
        .order_by(SchoolClass.grade_level, Section.name, Student.roll_no)
    )


@router.get("/academic-year/current", response_model=YearOut)
def current_academic_year(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    year_id = current_year_id(db)
    year = db.get(AcademicYear, year_id) if year_id else None
    if year is None:
        raise not_found("Current academic year")
    return YearOut(id=year.id, name=year.name, start_date=year.start_date, end_date=year.end_date)


@router.get("/classes", response_model=list[ClassOut])
def list_classes(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(SchoolClass).where(SchoolClass.is_active.is_(True)).order_by(SchoolClass.grade_level)
    sections = user_section_ids(user, db)
    if sections is not None:  # not admin: only classes of the sections this user can see
        stmt = stmt.where(SchoolClass.id.in_(user_class_ids(db, sections)))
    return [ClassOut(id=c.id, name=c.name, grade_level=c.grade_level) for c in db.scalars(stmt)]


@router.get("/sections", response_model=list[SectionOut])
def list_sections(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = (
        select(Section, SchoolClass.name)
        .join(SchoolClass, SchoolClass.id == Section.class_id)
        .where(Section.is_active.is_(True))
        .order_by(SchoolClass.grade_level, Section.name)
    )
    sections = user_section_ids(user, db)
    if sections is not None:
        stmt = stmt.where(Section.id.in_(sections))
    return [_section_out(r) for r in db.execute(stmt).all()]


@router.get("/subjects", response_model=list[SubjectOut])
def list_subjects(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stmt = select(Subject).where(Subject.is_active.is_(True)).order_by(Subject.name)
    return [SubjectOut(id=s.id, name=s.name, code=s.code) for s in db.scalars(stmt)]


@router.get("/teachers", response_model=list[TeacherOut])
def list_teachers(db: Session = Depends(get_db), user: User = Depends(require_roles("admin"))):
    stmt = (
        select(Teacher, User.full_name)
        .join(User, User.id == Teacher.user_id)
        .where(Teacher.is_active.is_(True))
        .order_by(User.full_name)
    )
    return [
        TeacherOut(id=t.id, user_id=t.user_id, full_name=name, employee_no=t.employee_no)
        for t, name in db.execute(stmt).all()
    ]


@router.get("/students", response_model=list[StudentOut])
def list_students(
    section_id: uuid.UUID | None = None,
    limit: int = Query(500, ge=1, le=1000),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin", "teacher")),  # students: 403; parents use /my-children
):
    stmt = _student_query()
    if section_id is not None:
        require_section_visible(user, db, section_id, "Section")  # teacher outside their sections -> 404
        stmt = stmt.where(Student.section_id == section_id)
    else:
        sections = user_section_ids(user, db)
        if sections is not None:
            stmt = stmt.where(Student.section_id.in_(sections))
    return [_student_out(r) for r in db.execute(stmt.limit(limit)).all()]


@router.get("/my-children", response_model=list[StudentOut])
def my_children(db: Session = Depends(get_db), user: User = Depends(require_roles("parent"))):
    stmt = (
        _student_query()
        .join(StudentParent, StudentParent.student_id == Student.id)
        .join(Parent, Parent.id == StudentParent.parent_id)
        .where(Parent.user_id == user.id)
    )
    return [_student_out(r) for r in db.execute(stmt).all()]


@router.get("/my-teaching", response_model=list[TeachingOut])
def my_teaching(db: Session = Depends(get_db), user: User = Depends(require_roles("teacher"))):
    teacher_id = teacher_id_for(user, db)

    def load(year_id: uuid.UUID | None):
        stmt = (
            select(TeacherAssignment, SchoolClass.name, Section.name, Subject.name)
            .join(Section, Section.id == TeacherAssignment.section_id)
            .join(SchoolClass, SchoolClass.id == Section.class_id)
            .join(Subject, Subject.id == TeacherAssignment.subject_id)
            .where(TeacherAssignment.teacher_id == teacher_id)
            .order_by(SchoolClass.grade_level, Section.name, Subject.name)
        )
        if year_id is not None:
            stmt = stmt.where(TeacherAssignment.academic_year_id == year_id)
        return db.execute(stmt).all()

    rows = load(current_year_id(db)) or load(None)  # current academic year preferred, else any
    return [
        TeachingOut(section_id=a.section_id, section_name=f"{class_name}-{section_name}",
                    subject_id=a.subject_id, subject_name=subject_name)
        for a, class_name, section_name, subject_name in rows
    ]


@router.get("/my-student", response_model=StudentOut)
def my_student(db: Session = Depends(get_db), user: User = Depends(require_roles("student"))):
    student_id = student_id_for(user, db)
    row = db.execute(_student_query().where(Student.id == student_id)).first()
    if row is None:
        raise AppError(404, "not_found", "Student record not found")
    return _student_out(row)
