"""Academic structure: academic years, classes, sections, subjects, teacher assignments."""
import uuid
from datetime import date
from typing import Self

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.common.scope import section_labels
from app.core.database import get_db
from app.core.errors import BadRequest, Conflict, NotFound, ValidationFailed, field_error
from app.core.security import get_current_user, require_roles
from app.modules.foundation.models import (
    AcademicYear, SchoolClass, Section, Student, Subject, Teacher, TeacherAssignment, User,
)

router = APIRouter(tags=["Academics"])
admin_only = Depends(require_roles("admin"))
authed = Depends(get_current_user)


# ====================================================================== academic years
class YearBody(BaseModel):
    name: str = Field(min_length=4, max_length=20)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _d(self) -> Self:
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self


class YearUpdate(BaseModel):
    name: str | None = Field(None, min_length=4, max_length=20)
    start_date: date | None = None
    end_date: date | None = None


def _year_out(y: AcademicYear) -> dict:
    return {"id": y.id, "name": y.name, "start_date": y.start_date, "end_date": y.end_date, "is_current": y.is_current}


@router.get("/academic-years")
def list_years(_: User = authed, db: Session = Depends(get_db)):
    return [_year_out(y) for y in db.scalars(select(AcademicYear).order_by(AcademicYear.start_date.desc()))]


@router.post("/academic-years", status_code=201)
def create_year(body: YearBody, _: User = admin_only, db: Session = Depends(get_db)):
    if db.scalar(select(AcademicYear.id).where(AcademicYear.name == body.name)):
        raise Conflict("An academic year with this name already exists")
    y = AcademicYear(name=body.name, start_date=body.start_date, end_date=body.end_date, is_current=False)
    db.add(y)
    db.commit()
    return _year_out(y)


@router.patch("/academic-years/{year_id}")
def update_year(year_id: uuid.UUID, body: YearUpdate, _: User = admin_only, db: Session = Depends(get_db)):
    y = db.get(AcademicYear, year_id)
    if y is None:
        raise NotFound("Academic year not found")
    data = body.model_dump(exclude_unset=True, exclude_none=True)
    for k, v in data.items():
        setattr(y, k, v)
    if y.end_date <= y.start_date:
        raise ValidationFailed(errors=[field_error("end_date", "end_date must be after start_date")])
    if "name" in data and db.scalar(select(AcademicYear.id).where(AcademicYear.name == y.name, AcademicYear.id != y.id)):
        raise Conflict("An academic year with this name already exists")
    db.commit()
    return _year_out(y)


@router.post("/academic-years/{year_id}/set-current")
def set_current_year(year_id: uuid.UUID, _: User = admin_only, db: Session = Depends(get_db)):
    y = db.get(AcademicYear, year_id)
    if y is None:
        raise NotFound("Academic year not found")
    db.execute(update(AcademicYear).where(AcademicYear.is_current).values(is_current=False))
    db.flush()
    y.is_current = True
    db.commit()
    return _year_out(y)


# ====================================================================== classes
class ClassBody(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    grade_level: int = Field(ge=0, le=12)


class ClassUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=50)
    grade_level: int | None = Field(None, ge=0, le=12)
    is_active: bool | None = None


def _class_out(db: Session, rows: list[SchoolClass]) -> list[dict]:
    secs = db.execute(select(Section.class_id, func.count()).where(Section.is_active).group_by(Section.class_id)).all()
    count = {r[0]: r[1] for r in secs}
    return [{"id": c.id, "name": c.name, "grade_level": c.grade_level, "is_active": c.is_active, "section_count": count.get(c.id, 0)}
            for c in rows]


@router.get("/classes")
def list_classes(include_inactive: bool = False, _: User = authed, db: Session = Depends(get_db)):
    stmt = select(SchoolClass).order_by(SchoolClass.grade_level, SchoolClass.name)
    if not include_inactive:
        stmt = stmt.where(SchoolClass.is_active)
    return _class_out(db, list(db.scalars(stmt)))


@router.post("/classes", status_code=201)
def create_class(body: ClassBody, _: User = admin_only, db: Session = Depends(get_db)):
    if db.scalar(select(SchoolClass.id).where(func.lower(SchoolClass.name) == body.name.strip().lower())):
        raise Conflict("A class with this name already exists")
    c = SchoolClass(name=body.name.strip(), grade_level=body.grade_level)
    db.add(c)
    db.commit()
    return _class_out(db, [c])[0]


@router.patch("/classes/{class_id}")
def update_class(class_id: uuid.UUID, body: ClassUpdate, _: User = admin_only, db: Session = Depends(get_db)):
    c = db.get(SchoolClass, class_id)
    if c is None:
        raise NotFound("Class not found")
    data = body.model_dump(exclude_unset=True, exclude_none=True)
    if "name" in data and db.scalar(select(SchoolClass.id).where(func.lower(SchoolClass.name) == data["name"].strip().lower(), SchoolClass.id != c.id)):
        raise Conflict("A class with this name already exists")
    if data.get("is_active") is False and db.scalar(
            select(Student.id).join(Section, Section.id == Student.section_id).where(Section.class_id == c.id, Student.is_active).limit(1)):
        raise Conflict("The class still has active students; move them first", code="class_in_use")
    for k, v in data.items():
        setattr(c, k, v)
    if data.get("is_active") is False:
        db.execute(update(Section).where(Section.class_id == c.id).values(is_active=False))
    db.commit()
    return _class_out(db, [c])[0]


# ====================================================================== sections
class SectionBody(BaseModel):
    class_id: uuid.UUID
    name: str = Field(min_length=1, max_length=10)
    class_teacher_id: uuid.UUID | None = None


class SectionUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=10)
    class_teacher_id: uuid.UUID | None = None
    is_active: bool | None = None


def _section_out(db: Session, rows: list[Section]) -> list[dict]:
    labels = section_labels(db, [s.id for s in rows])
    counts = {r[0]: r[1] for r in db.execute(select(Student.section_id, func.count()).where(Student.is_active).group_by(Student.section_id))}
    tnames = {r[0]: r[1] for r in db.execute(select(Teacher.id, User.full_name).join(User, User.id == Teacher.user_id)
                                              .where(Teacher.id.in_([s.class_teacher_id for s in rows if s.class_teacher_id])))} if rows else {}
    return [{"id": s.id, "class_id": s.class_id, "name": s.name, "label": labels.get(s.id), "class_teacher_id": s.class_teacher_id,
             "class_teacher_name": tnames.get(s.class_teacher_id), "student_count": counts.get(s.id, 0), "is_active": s.is_active}
            for s in rows]


def _check_class_teacher(db: Session, tid: uuid.UUID | None) -> None:
    if tid is not None:
        t = db.get(Teacher, tid)
        if t is None or not t.is_active:
            raise ValidationFailed(errors=[field_error("class_teacher_id", "Teacher does not exist or is inactive")])


@router.get("/sections")
def list_sections(class_id: uuid.UUID | None = None, include_inactive: bool = False, _: User = authed, db: Session = Depends(get_db)):
    stmt = select(Section).join(SchoolClass, SchoolClass.id == Section.class_id).order_by(SchoolClass.grade_level, Section.name)
    if class_id:
        stmt = stmt.where(Section.class_id == class_id)
    if not include_inactive:
        stmt = stmt.where(Section.is_active)
    return _section_out(db, list(db.scalars(stmt)))


@router.post("/sections", status_code=201)
def create_section(body: SectionBody, _: User = admin_only, db: Session = Depends(get_db)):
    c = db.get(SchoolClass, body.class_id)
    if c is None or not c.is_active:
        raise ValidationFailed(errors=[field_error("class_id", "Class does not exist or is inactive")])
    if db.scalar(select(Section.id).where(Section.class_id == c.id, func.lower(Section.name) == body.name.strip().lower())):
        raise Conflict("This section already exists in the class")
    _check_class_teacher(db, body.class_teacher_id)
    s = Section(class_id=c.id, name=body.name.strip().upper(), class_teacher_id=body.class_teacher_id)
    db.add(s)
    db.commit()
    return _section_out(db, [s])[0]


@router.patch("/sections/{section_id}")
def update_section(section_id: uuid.UUID, body: SectionUpdate, _: User = admin_only, db: Session = Depends(get_db)):
    s = db.get(Section, section_id)
    if s is None:
        raise NotFound("Section not found")
    data = body.model_dump(exclude_unset=True)
    if data.get("name") and db.scalar(select(Section.id).where(Section.class_id == s.class_id, func.lower(Section.name) == data["name"].strip().lower(), Section.id != s.id)):
        raise Conflict("This section already exists in the class")
    if "class_teacher_id" in data:
        _check_class_teacher(db, data["class_teacher_id"])
    if data.get("is_active") is False and db.scalar(select(Student.id).where(Student.section_id == s.id, Student.is_active).limit(1)):
        raise Conflict("The section still has active students; move them first", code="section_in_use")
    for k, v in data.items():
        if v is None and k in ("name", "is_active"):
            continue
        setattr(s, k, v.strip().upper() if k == "name" else v)
    db.commit()
    return _section_out(db, [s])[0]


# ====================================================================== subjects
class SubjectBody(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    code: str = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")


class SubjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    code: str | None = Field(None, min_length=2, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    is_active: bool | None = None


def _subject_out(s: Subject) -> dict:
    return {"id": s.id, "name": s.name, "code": s.code, "is_active": s.is_active}


@router.get("/subjects")
def list_subjects(include_inactive: bool = False, _: User = authed, db: Session = Depends(get_db)):
    stmt = select(Subject).order_by(Subject.name)
    if not include_inactive:
        stmt = stmt.where(Subject.is_active)
    return [_subject_out(s) for s in db.scalars(stmt)]


@router.post("/subjects", status_code=201)
def create_subject(body: SubjectBody, _: User = admin_only, db: Session = Depends(get_db)):
    code = body.code.upper()
    if db.scalar(select(Subject.id).where(Subject.code == code)):
        raise Conflict(f"Subject code '{code}' already exists", code="subject_code_taken")
    s = Subject(name=body.name.strip(), code=code)
    db.add(s)
    db.commit()
    return _subject_out(s)


@router.patch("/subjects/{subject_id}")
def update_subject(subject_id: uuid.UUID, body: SubjectUpdate, _: User = admin_only, db: Session = Depends(get_db)):
    s = db.get(Subject, subject_id)
    if s is None:
        raise NotFound("Subject not found")
    data = body.model_dump(exclude_unset=True, exclude_none=True)
    if "code" in data:
        data["code"] = data["code"].upper()
        if db.scalar(select(Subject.id).where(Subject.code == data["code"], Subject.id != s.id)):
            raise Conflict("Subject code already exists", code="subject_code_taken")
    for k, v in data.items():
        setattr(s, k, v)
    db.commit()
    return _subject_out(s)


# ====================================================================== teacher assignments
class AssignmentBody(BaseModel):
    teacher_id: uuid.UUID
    section_id: uuid.UUID
    subject_id: uuid.UUID
    academic_year_id: uuid.UUID | None = None


class AssignmentUpdate(BaseModel):
    teacher_id: uuid.UUID


def _assign_out(db: Session, rows: list[TeacherAssignment]) -> list[dict]:
    labels = section_labels(db, [a.section_id for a in rows])
    t = {r[0]: r[1] for r in db.execute(select(Teacher.id, User.full_name).join(User, User.id == Teacher.user_id))}
    s = {r.id: r.name for r in db.execute(select(Subject.id, Subject.name))}
    return [{"id": a.id, "teacher_id": a.teacher_id, "teacher_name": t.get(a.teacher_id), "section_id": a.section_id,
             "section_label": labels.get(a.section_id), "subject_id": a.subject_id, "subject_name": s.get(a.subject_id),
             "academic_year_id": a.academic_year_id} for a in rows]


@router.get("/teacher-assignments")
def list_assignments(teacher_id: uuid.UUID | None = None, section_id: uuid.UUID | None = None,
                     academic_year_id: uuid.UUID | None = None, _: User = Depends(require_roles("admin", "teacher")),
                     db: Session = Depends(get_db)):
    stmt = select(TeacherAssignment)
    yid = academic_year_id or db.scalar(select(AcademicYear.id).where(AcademicYear.is_current))
    if yid:
        stmt = stmt.where(TeacherAssignment.academic_year_id == yid)
    if teacher_id:
        stmt = stmt.where(TeacherAssignment.teacher_id == teacher_id)
    if section_id:
        stmt = stmt.where(TeacherAssignment.section_id == section_id)
    return _assign_out(db, list(db.scalars(stmt)))


@router.post("/teacher-assignments", status_code=201)
def create_assignment(body: AssignmentBody, _: User = admin_only, db: Session = Depends(get_db)):
    t, sec, sub = db.get(Teacher, body.teacher_id), db.get(Section, body.section_id), db.get(Subject, body.subject_id)
    errors = []
    if t is None or not t.is_active:
        errors.append(field_error("teacher_id", "Teacher does not exist or is inactive"))
    if sec is None or not sec.is_active:
        errors.append(field_error("section_id", "Section does not exist or is inactive"))
    if sub is None or not sub.is_active:
        errors.append(field_error("subject_id", "Subject does not exist or is inactive"))
    yid = body.academic_year_id or db.scalar(select(AcademicYear.id).where(AcademicYear.is_current))
    if yid is None or db.get(AcademicYear, yid) is None:
        errors.append(field_error("academic_year_id", "No such academic year (and no current year is set)"))
    if errors:
        raise ValidationFailed(errors=errors)
    if db.scalar(select(TeacherAssignment.id).where(TeacherAssignment.section_id == sec.id, TeacherAssignment.subject_id == sub.id,
                                                    TeacherAssignment.academic_year_id == yid)):
        raise Conflict("This subject already has a teacher in that section for the year", code="assignment_exists")
    a = TeacherAssignment(teacher_id=t.id, section_id=sec.id, subject_id=sub.id, academic_year_id=yid)
    db.add(a)
    db.commit()
    return _assign_out(db, [a])[0]


@router.patch("/teacher-assignments/{assignment_id}")
def reassign(assignment_id: uuid.UUID, body: AssignmentUpdate, _: User = admin_only, db: Session = Depends(get_db)):
    a = db.get(TeacherAssignment, assignment_id)
    if a is None:
        raise NotFound("Assignment not found")
    t = db.get(Teacher, body.teacher_id)
    if t is None or not t.is_active:
        raise ValidationFailed(errors=[field_error("teacher_id", "Teacher does not exist or is inactive")])
    a.teacher_id = t.id
    db.commit()
    return _assign_out(db, [a])[0]


@router.delete("/teacher-assignments/{assignment_id}", status_code=204)
def delete_assignment(assignment_id: uuid.UUID, _: User = admin_only, db: Session = Depends(get_db)):
    a = db.get(TeacherAssignment, assignment_id)
    if a is None:
        raise NotFound("Assignment not found")
    db.delete(a)
    db.commit()
