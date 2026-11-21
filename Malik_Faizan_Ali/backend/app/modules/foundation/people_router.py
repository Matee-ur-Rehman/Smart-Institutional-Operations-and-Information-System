"""Teachers, students, parents and the parent-child links (API: /teachers, /students, /parents)."""
import re
import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.orm import Session

from app.common.pagination import Page, PageParams, page_params, paginate
from app.common.scope import current_year, section_labels
from app.core.access import can_access_student, teacher_id_for
from app.core.database import get_db
from app.core.errors import BadRequest, Conflict, Forbidden, NotFound, ValidationFailed, field_error
from app.core.security import get_current_user, require_roles
from app.modules.foundation.accounts import CNIC_PATTERN, PHONE_PATTERN, create_user
from app.modules.foundation.auth_router import check_password_strength, revoke_all_tokens
from app.modules.foundation.models import (
    Parent, Section, SchoolClass, Student, StudentParent, Subject, Teacher, TeacherAssignment, User,
)
from app.modules.foundation.users_router import sync_profile_active

router = APIRouter(tags=["People"])
admin_only = Depends(require_roles("admin"))
admin_teacher = Depends(require_roles("admin", "teacher"))
Relation = Literal["father", "mother", "guardian"]
Password = Field(None, min_length=8, max_length=128)
ROLL_RE = re.compile(r"^[A-Za-z0-9/_-]{1,30}$")


def _strong(v):
    return check_password_strength(v) if v else v


# ====================================================================== teachers
class TeacherCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    employee_no: str = Field(min_length=1, max_length=30)
    login_id: str | None = Field(None, min_length=3, max_length=50)
    password: str | None = Password
    email: EmailStr | None = None
    phone: str | None = Field(None, pattern=PHONE_PATTERN)
    qualification: str | None = Field(None, max_length=150)
    joining_date: date | None = None
    _s = field_validator("password")(_strong)


class TeacherUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=150)
    employee_no: str | None = Field(None, min_length=1, max_length=30)
    email: EmailStr | None = None
    phone: str | None = Field(None, pattern=PHONE_PATTERN)
    qualification: str | None = Field(None, max_length=150)
    joining_date: date | None = None
    is_active: bool | None = None


def _teacher_dict(db: Session, teachers: list[Teacher], detail: bool = False) -> list[dict]:
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_([t.user_id for t in teachers])))}
    out = []
    assign: dict[uuid.UUID, list] = {}
    class_of: dict[uuid.UUID, list] = {}
    if detail and teachers:
        ids = [t.id for t in teachers]
        yr = current_year(db).id
        rows = db.execute(select(TeacherAssignment, Subject.name).join(Subject, Subject.id == TeacherAssignment.subject_id)
                          .where(TeacherAssignment.teacher_id.in_(ids), TeacherAssignment.academic_year_id == yr)).all()
        labels = section_labels(db, [r[0].section_id for r in rows])
        for a, sname in rows:
            assign.setdefault(a.teacher_id, []).append({"id": a.id, "section_id": a.section_id, "section_label": labels.get(a.section_id),
                                                       "subject_id": a.subject_id, "subject_name": sname})
        for sec in db.scalars(select(Section).where(Section.class_teacher_id.in_(ids))):
            class_of.setdefault(sec.class_teacher_id, []).append(
                {"section_id": sec.id, "section_label": section_labels(db, [sec.id]).get(sec.id)})
    for t in teachers:
        u = users[t.user_id]
        d = {"id": t.id, "user_id": u.id, "login_id": u.login_id, "full_name": u.full_name, "email": u.email, "phone": u.phone,
             "employee_no": t.employee_no, "qualification": t.qualification, "joining_date": t.joining_date,
             "is_active": t.is_active and u.is_active}
        if detail:
            d["assignments"] = assign.get(t.id, [])
            d["class_teacher_of"] = class_of.get(t.id, [])
        out.append(d)
    return out


@router.post("/teachers", status_code=201)
def create_teacher(body: TeacherCreate, _: User = admin_only, db: Session = Depends(get_db)):
    if db.scalar(select(Teacher.id).where(func.lower(Teacher.employee_no) == body.employee_no.lower())):
        raise Conflict(f"Employee number '{body.employee_no}' already exists", code="employee_no_taken")
    user, temp = create_user(db, role="teacher", login_id=body.login_id or body.employee_no.lower(), full_name=body.full_name,
                             password=body.password, email=body.email, phone=body.phone)
    t = Teacher(user_id=user.id, employee_no=body.employee_no.strip(), qualification=body.qualification, joining_date=body.joining_date)
    db.add(t)
    db.commit()
    return {**_teacher_dict(db, [t], True)[0], "temporary_password": temp}


@router.get("/teachers")
def list_teachers(q: str | None = Query(None, max_length=100), is_active: bool | None = None,
                  params: PageParams = Depends(page_params), _: User = admin_only, db: Session = Depends(get_db)):
    stmt = select(Teacher).join(User, User.id == Teacher.user_id)
    if is_active is not None:
        stmt = stmt.where(Teacher.is_active == is_active)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.full_name.ilike(like), Teacher.employee_no.ilike(like), User.login_id.ilike(like)))
    rows, total = paginate(db, stmt.order_by(User.full_name), params)
    return {"items": _teacher_dict(db, [r[0] for r in rows]), "total": total, "page": params.page, "page_size": params.page_size}


def _teacher(db: Session, user: User, teacher_id: uuid.UUID) -> Teacher:
    t = db.get(Teacher, teacher_id)
    if t is None or (user.role != "admin" and t.user_id != user.id):
        raise NotFound("Teacher not found")
    return t


@router.get("/teachers/{teacher_id}")
def get_teacher(teacher_id: uuid.UUID, user: User = Depends(require_roles("admin", "teacher")), db: Session = Depends(get_db)):
    return _teacher_dict(db, [_teacher(db, user, teacher_id)], True)[0]


@router.patch("/teachers/{teacher_id}")
def update_teacher(teacher_id: uuid.UUID, body: TeacherUpdate, me: User = admin_only, db: Session = Depends(get_db)):
    t = _teacher(db, me, teacher_id)
    u = db.get(User, t.user_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("employee_no") and db.scalar(select(Teacher.id).where(func.lower(Teacher.employee_no) == data["employee_no"].lower(), Teacher.id != t.id)):
        raise Conflict("Employee number already exists", code="employee_no_taken")
    if data.get("email") and db.scalar(select(User.id).where(func.lower(User.email) == data["email"].lower(), User.id != u.id)):
        raise Conflict("This email is already used by another account", code="email_taken")
    for k in ("full_name", "email", "phone"):
        if k in data:
            setattr(u, k, data[k])
    for k in ("employee_no", "qualification", "joining_date"):
        if k in data:
            setattr(t, k, data[k])
    if "is_active" in data:
        t.is_active = u.is_active = data["is_active"]
        if not t.is_active:
            revoke_all_tokens(db, u.id)
    db.commit()
    return _teacher_dict(db, [t], True)[0]


# ====================================================================== students
class ParentLinkIn(BaseModel):
    parent_id: uuid.UUID
    relation: Relation = "guardian"


class StudentCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    roll_no: str = Field(min_length=1, max_length=30)
    section_id: uuid.UUID
    date_of_birth: date | None = None
    gender: Literal["male", "female", "other"] | None = None
    admission_date: date | None = None
    address: str | None = Field(None, max_length=300)
    create_login: bool = True
    login_id: str | None = Field(None, min_length=3, max_length=50)
    password: str | None = Password
    email: EmailStr | None = None
    phone: str | None = Field(None, pattern=PHONE_PATTERN)
    parents: list[ParentLinkIn] = Field(default_factory=list, max_length=4)
    _s = field_validator("password")(_strong)

    @model_validator(mode="after")
    def _check(self):
        if not ROLL_RE.match(self.roll_no):
            raise ValueError("roll_no may only contain letters, digits, '/', '_' and '-'")
        if self.date_of_birth and not (date(1990, 1, 1) <= self.date_of_birth <= date.today()):
            raise ValueError("date_of_birth is not a valid past date")
        return self


class StudentUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=150)
    roll_no: str | None = Field(None, min_length=1, max_length=30)
    section_id: uuid.UUID | None = None
    date_of_birth: date | None = None
    gender: Literal["male", "female", "other"] | None = None
    admission_date: date | None = None
    address: str | None = Field(None, max_length=300)
    is_active: bool | None = None


class StudentLogin(BaseModel):
    login_id: str | None = Field(None, min_length=3, max_length=50)
    password: str | None = Password
    _s = field_validator("password")(_strong)


def _student_dicts(db: Session, user: User, students: list[Student], detail: bool = False) -> list[dict]:
    labels = section_labels(db, [s.section_id for s in students])
    sec = {r[0]: (r[1], r[2]) for r in db.execute(
        select(Section.id, SchoolClass.id, SchoolClass.name).join(SchoolClass, SchoolClass.id == Section.class_id)
        .where(Section.id.in_({s.section_id for s in students})))} if students else {}
    logins = {u.id: u.login_id for u in db.scalars(select(User).where(User.id.in_([s.user_id for s in students if s.user_id])))} if students else {}
    parents: dict[uuid.UUID, list] = {}
    if detail and students:
        rows = db.execute(select(StudentParent, Parent, User).join(Parent, Parent.id == StudentParent.parent_id)
                          .join(User, User.id == Parent.user_id).where(StudentParent.student_id.in_([s.id for s in students]))).all()
        for link, p, u in rows:
            parents.setdefault(link.student_id, []).append({
                "parent_id": p.id, "full_name": u.full_name, "relation": link.relation,
                "phone": u.phone if user.role in ("admin", "teacher") else None})
    out = []
    for s in students:
        cid, cname = sec.get(s.section_id, (None, None))
        d = {"id": s.id, "user_id": s.user_id, "login_id": logins.get(s.user_id), "roll_no": s.roll_no, "full_name": s.full_name,
             "section_id": s.section_id, "section_label": labels.get(s.section_id), "class_id": cid, "class_name": cname,
             "is_active": s.is_active, "date_of_birth": s.date_of_birth, "gender": s.gender, "admission_date": s.admission_date,
             "address": s.address}
        if detail:
            d["parents"] = parents.get(s.id, [])
        out.append(d)
    return out


def _active_section(db: Session, section_id: uuid.UUID) -> Section:
    sec = db.get(Section, section_id)
    if sec is None or not sec.is_active:
        raise ValidationFailed(errors=[field_error("section_id", "Section does not exist or is inactive")])
    return sec


def _link(db: Session, student_id: uuid.UUID, link: ParentLinkIn) -> None:
    if db.get(Parent, link.parent_id) is None:
        raise ValidationFailed(errors=[field_error("parents", "Parent does not exist")])
    if db.get(StudentParent, (student_id, link.parent_id)) is not None:
        raise Conflict("This parent is already linked to the student", code="already_linked")
    db.add(StudentParent(student_id=student_id, parent_id=link.parent_id, relation=link.relation))


@router.post("/students", status_code=201)
def create_student(body: StudentCreate, me: User = admin_only, db: Session = Depends(get_db)):
    _active_section(db, body.section_id)
    if db.scalar(select(Student.id).where(func.lower(Student.roll_no) == body.roll_no.lower())):
        raise Conflict(f"Roll number '{body.roll_no}' already exists", code="roll_no_taken")
    if len({p.parent_id for p in body.parents}) != len(body.parents):
        raise ValidationFailed(errors=[field_error("parents", "Duplicate parent in list")])
    user = temp = None
    if body.create_login:
        user, temp = create_user(db, role="student", login_id=body.login_id or body.roll_no.lower().replace("/", "-"),
                                 full_name=body.full_name, password=body.password, email=body.email, phone=body.phone)
    st = Student(user_id=user.id if user else None, roll_no=body.roll_no.strip(), full_name=body.full_name.strip(),
                 section_id=body.section_id, date_of_birth=body.date_of_birth, gender=body.gender,
                 admission_date=body.admission_date or date.today(), address=body.address)
    db.add(st)
    db.flush()
    for link in body.parents:
        _link(db, st.id, link)
    db.commit()
    out = _student_dicts(db, me, [st], True)[0]
    out["temporary_password"] = temp
    return out


@router.get("/students")
def list_students(section_id: uuid.UUID | None = None, class_id: uuid.UUID | None = None, q: str | None = Query(None, max_length=100),
                  is_active: bool | None = None, params: PageParams = Depends(page_params),
                  user: User = admin_teacher, db: Session = Depends(get_db)):
    stmt = select(Student)
    if user.role == "teacher":
        tid = teacher_id_for(user, db)
        mine = select(TeacherAssignment.section_id).where(TeacherAssignment.teacher_id == tid,
                                                          TeacherAssignment.academic_year_id == current_year(db).id)
        stmt = stmt.where(Student.section_id.in_(mine), Student.is_active)
    elif is_active is not None:
        stmt = stmt.where(Student.is_active == is_active)
    if section_id:
        stmt = stmt.where(Student.section_id == section_id)
    if class_id:
        stmt = stmt.join(Section, Section.id == Student.section_id).where(Section.class_id == class_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Student.full_name.ilike(like), Student.roll_no.ilike(like)))
    rows, total = paginate(db, stmt.order_by(Student.roll_no), params)
    return {"items": _student_dicts(db, user, [r[0] for r in rows]), "total": total, "page": params.page, "page_size": params.page_size}


def _student(db: Session, user: User, student_id: uuid.UUID) -> Student:
    st = db.get(Student, student_id)
    if st is None or not can_access_student(user, student_id, db):
        raise NotFound("Student not found")
    return st


@router.get("/students/{student_id}")
def get_student(student_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _student_dicts(db, user, [_student(db, user, student_id)], True)[0]


@router.patch("/students/{student_id}")
def update_student(student_id: uuid.UUID, body: StudentUpdate, me: User = admin_only, db: Session = Depends(get_db)):
    st = _student(db, me, student_id)
    data = body.model_dump(exclude_unset=True)
    if "roll_no" in data:
        if not ROLL_RE.match(data["roll_no"] or ""):
            raise ValidationFailed(errors=[field_error("roll_no", "Letters, digits, '/', '_' and '-' only")])
        if db.scalar(select(Student.id).where(func.lower(Student.roll_no) == data["roll_no"].lower(), Student.id != st.id)):
            raise Conflict("Roll number already exists", code="roll_no_taken")
    if data.get("section_id"):
        _active_section(db, data["section_id"])
    if data.get("date_of_birth") and not (date(1990, 1, 1) <= data["date_of_birth"] <= date.today()):
        raise ValidationFailed(errors=[field_error("date_of_birth", "Not a valid past date")])
    for k, v in data.items():
        if v is None and k in ("full_name", "roll_no", "section_id", "is_active"):
            continue
        setattr(st, k, v)
    if st.user_id:
        u = db.get(User, st.user_id)
        if "full_name" in data and data["full_name"]:
            u.full_name = data["full_name"]
        if data.get("is_active") is not None:
            u.is_active = data["is_active"]
            if not u.is_active:
                revoke_all_tokens(db, u.id)
    db.commit()
    return _student_dicts(db, me, [st], True)[0]


@router.post("/students/{student_id}/login", status_code=201)
def create_student_login(student_id: uuid.UUID, body: StudentLogin | None = None, me: User = admin_only, db: Session = Depends(get_db)):
    st = _student(db, me, student_id)
    if st.user_id:
        raise Conflict("This student already has a login", code="login_exists")
    body = body or StudentLogin()
    user, temp = create_user(db, role="student", login_id=body.login_id or st.roll_no.lower().replace("/", "-"),
                             full_name=st.full_name, password=body.password)
    st.user_id = user.id
    db.commit()
    return {"login_id": user.login_id, "temporary_password": temp}


@router.post("/students/{student_id}/parents", status_code=201)
def link_parent(student_id: uuid.UUID, body: ParentLinkIn, me: User = admin_only, db: Session = Depends(get_db)):
    st = _student(db, me, student_id)
    _link(db, st.id, body)
    db.commit()
    return _student_dicts(db, me, [st], True)[0]


@router.delete("/students/{student_id}/parents/{parent_id}", status_code=204)
def unlink_parent(student_id: uuid.UUID, parent_id: uuid.UUID, me: User = admin_only, db: Session = Depends(get_db)):
    _student(db, me, student_id)
    res = db.execute(delete(StudentParent).where(StudentParent.student_id == student_id, StudentParent.parent_id == parent_id))
    if res.rowcount == 0:
        raise NotFound("Link not found")
    db.commit()


# ====================================================================== parents
class ChildLinkIn(BaseModel):
    student_id: uuid.UUID
    relation: Relation = "guardian"


class ParentCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    login_id: str = Field(min_length=3, max_length=50)
    password: str | None = Password
    email: EmailStr | None = None
    phone: str = Field(pattern=PHONE_PATTERN)
    cnic: str | None = Field(None, pattern=CNIC_PATTERN)
    address: str | None = Field(None, max_length=300)
    occupation: str | None = Field(None, max_length=100)
    children: list[ChildLinkIn] = Field(default_factory=list, max_length=10)
    _s = field_validator("password")(_strong)


class ParentUpdate(BaseModel):
    full_name: str | None = Field(None, min_length=2, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(None, pattern=PHONE_PATTERN)
    cnic: str | None = Field(None, pattern=CNIC_PATTERN)
    address: str | None = Field(None, max_length=300)
    occupation: str | None = Field(None, max_length=100)
    is_active: bool | None = None


def _parent_dicts(db: Session, parents: list[Parent]) -> list[dict]:
    users = {u.id: u for u in db.scalars(select(User).where(User.id.in_([p.user_id for p in parents])))}
    kids: dict[uuid.UUID, list] = {}
    if parents:
        rows = db.execute(select(StudentParent, Student).join(Student, Student.id == StudentParent.student_id)
                          .where(StudentParent.parent_id.in_([p.id for p in parents])).order_by(Student.roll_no)).all()
        labels = section_labels(db, [r[1].section_id for r in rows])
        for link, s in rows:
            kids.setdefault(link.parent_id, []).append({"student_id": s.id, "full_name": s.full_name, "roll_no": s.roll_no,
                                                        "section_label": labels.get(s.section_id), "relation": link.relation})
    out = []
    for p in parents:
        u = users[p.user_id]
        out.append({"id": p.id, "user_id": u.id, "login_id": u.login_id, "full_name": u.full_name, "email": u.email, "phone": u.phone,
                    "cnic": p.cnic, "address": p.address, "occupation": p.occupation, "is_active": u.is_active,
                    "children": kids.get(p.id, [])})
    return out


@router.post("/parents", status_code=201)
def create_parent(body: ParentCreate, _: User = admin_only, db: Session = Depends(get_db)):
    if body.cnic and db.scalar(select(Parent.id).where(Parent.cnic == body.cnic)):
        raise Conflict("A parent with this CNIC already exists", code="cnic_taken")
    for c in body.children:
        if db.get(Student, c.student_id) is None:
            raise ValidationFailed(errors=[field_error("children", "Student does not exist")])
    if len({c.student_id for c in body.children}) != len(body.children):
        raise ValidationFailed(errors=[field_error("children", "Duplicate student in list")])
    user, temp = create_user(db, role="parent", login_id=body.login_id, full_name=body.full_name, password=body.password,
                             email=body.email, phone=body.phone)
    p = Parent(user_id=user.id, cnic=body.cnic, address=body.address, occupation=body.occupation)
    db.add(p)
    db.flush()
    for c in body.children:
        db.add(StudentParent(student_id=c.student_id, parent_id=p.id, relation=c.relation))
    db.commit()
    return {**_parent_dicts(db, [p])[0], "temporary_password": temp}


@router.get("/parents")
def list_parents(q: str | None = Query(None, max_length=100), params: PageParams = Depends(page_params),
                 _: User = admin_only, db: Session = Depends(get_db)):
    stmt = select(Parent).join(User, User.id == Parent.user_id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(User.full_name.ilike(like), User.login_id.ilike(like), User.phone.ilike(like), Parent.cnic.ilike(like)))
    rows, total = paginate(db, stmt.order_by(User.full_name), params)
    return {"items": _parent_dicts(db, [r[0] for r in rows]), "total": total, "page": params.page, "page_size": params.page_size}


@router.get("/parents/{parent_id}")
def get_parent(parent_id: uuid.UUID, _: User = admin_only, db: Session = Depends(get_db)):
    p = db.get(Parent, parent_id)
    if p is None:
        raise NotFound("Parent not found")
    return _parent_dicts(db, [p])[0]


@router.patch("/parents/{parent_id}")
def update_parent(parent_id: uuid.UUID, body: ParentUpdate, _: User = admin_only, db: Session = Depends(get_db)):
    p = db.get(Parent, parent_id)
    if p is None:
        raise NotFound("Parent not found")
    u = db.get(User, p.user_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("email") and db.scalar(select(User.id).where(func.lower(User.email) == data["email"].lower(), User.id != u.id)):
        raise Conflict("This email is already used by another account", code="email_taken")
    if data.get("cnic") and db.scalar(select(Parent.id).where(Parent.cnic == data["cnic"], Parent.id != p.id)):
        raise Conflict("A parent with this CNIC already exists", code="cnic_taken")
    for k in ("full_name", "email", "phone"):
        if k in data and data[k] is not None:
            setattr(u, k, data[k])
    for k in ("cnic", "address", "occupation"):
        if k in data:
            setattr(p, k, data[k])
    if data.get("is_active") is not None:
        u.is_active = data["is_active"]
        if not u.is_active:
            revoke_all_tokens(db, u.id)
    db.commit()
    return _parent_dicts(db, [p])[0]
