"""
Read-only, role-scoped lookup lists used by the Flutter dropdowns (sections, subjects, students, ...).

Convenience endpoints owned by Member 2. They only READ Member 1's tables and expose nothing that the
caller could not already see through the module endpoints. If Member 1 ships equivalent list endpoints
(/classes, /sections, /subjects, /students) the apps can be switched over and this module deleted.
"""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.scope import (
    child_section_ids, current_year, own_student, section_labels, teacher_pairs, visible_section_ids,
)
from app.core.access import parent_child_ids
from app.core.database import get_db
from app.core.errors import NotFound
from app.core.security import get_current_user, require_roles
from app.modules.foundation.models import (
    SchoolClass, Section, Student, Subject, Teacher, TeacherAssignment, User,
)

router = APIRouter(prefix="/lookups", tags=["Lookups (dropdown data)"])
admin_only = Depends(require_roles("admin"))
staff = Depends(require_roles("admin", "teacher"))


def _section_rows(db: Session, ids: set[uuid.UUID] | None) -> list[dict]:
    stmt = (select(Section.id, Section.name, Section.class_id, SchoolClass.name, SchoolClass.grade_level)
            .join(SchoolClass, SchoolClass.id == Section.class_id)
            .where(Section.is_active, SchoolClass.is_active)
            .order_by(SchoolClass.grade_level, Section.name))
    if ids is not None:
        stmt = stmt.where(Section.id.in_(list(ids) or [uuid.UUID(int=0)]))
    return [{"id": r[0], "label": f"{r[3]}-{r[1]}", "section_name": r[1], "class_id": r[2], "class_name": r[3],
             "grade_level": r[4]} for r in db.execute(stmt).all()]


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The caller's own profile ids (teacher_id / student_id / children) so the apps need no guesswork."""
    out: dict = {"user_id": user.id, "role": user.role, "full_name": user.full_name,
                 "teacher_id": None, "student": None, "children": []}
    if user.role == "teacher":
        out["teacher_id"] = db.scalar(select(Teacher.id).where(Teacher.user_id == user.id, Teacher.is_active))
    elif user.role == "student":
        st = own_student(user, db)
        if st:
            out["student"] = {"student_id": st.id, "roll_no": st.roll_no, "full_name": st.full_name,
                              "section_id": st.section_id,
                              "section_label": section_labels(db, [st.section_id]).get(st.section_id)}
    elif user.role == "parent":
        out["children"] = children(user=user, db=db)
    return out


@router.get("/academic-year")
def academic_year(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    y = current_year(db)
    return {"id": y.id, "name": y.name, "start_date": y.start_date, "end_date": y.end_date}


@router.get("/classes")
def classes(user: User = staff, db: Session = Depends(get_db)):
    rows = db.scalars(select(SchoolClass).where(SchoolClass.is_active).order_by(SchoolClass.grade_level)).all()
    return [{"id": c.id, "name": c.name, "grade_level": c.grade_level} for c in rows]


@router.get("/sections")
def sections(scope: str = Query("visible", pattern="^(visible|all)$"), user: User = Depends(get_current_user),
             db: Session = Depends(get_db)):
    """`visible` (default): the sections the caller works with (teacher: taught; student: own; parent: children's).
    `all`: every section, for admins and for teachers who need to browse other timetables."""
    if scope == "all" and user.role in ("admin", "teacher"):
        return _section_rows(db, None)
    return _section_rows(db, visible_section_ids(user, db))


@router.get("/subjects")
def subjects(section_id: uuid.UUID | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Admin: all subjects (or those taught in `section_id`). Teacher: only the subjects they teach (in `section_id`)."""
    stmt = select(Subject.id, Subject.name, Subject.code).where(Subject.is_active).order_by(Subject.name)
    if user.role == "teacher":
        tid = db.scalar(select(Teacher.id).where(Teacher.user_id == user.id, Teacher.is_active))
        pairs = teacher_pairs(db, tid) if tid else set()
        ids = {sub for sec, sub in pairs if section_id is None or sec == section_id}
        stmt = stmt.where(Subject.id.in_(list(ids) or [uuid.UUID(int=0)]))
    elif user.role == "admin" and section_id:
        stmt = stmt.where(Subject.id.in_(select(TeacherAssignment.subject_id).where(
            TeacherAssignment.section_id == section_id, TeacherAssignment.academic_year_id == current_year(db).id)))
    elif user.role in ("student", "parent"):
        sections_ = visible_section_ids(user, db) or set()
        stmt = stmt.where(Subject.id.in_(select(TeacherAssignment.subject_id).where(
            TeacherAssignment.section_id.in_(list(sections_) or [uuid.UUID(int=0)]))))
    return [{"id": r[0], "name": r[1], "code": r[2]} for r in db.execute(stmt).all()]


@router.get("/my-assignments")
def my_assignments(user: User = Depends(require_roles("teacher")), db: Session = Depends(get_db)):
    """(section, subject) pairs the logged-in teacher teaches this year."""
    tid = db.scalar(select(Teacher.id).where(Teacher.user_id == user.id, Teacher.is_active))
    pairs = teacher_pairs(db, tid) if tid else set()
    secs = section_labels(db, {s for s, _ in pairs})
    names = dict(db.execute(select(Subject.id, Subject.name)).all())
    out = [{"section_id": s, "section_label": secs.get(s), "subject_id": sub, "subject_name": names.get(sub)}
           for s, sub in pairs]
    return sorted(out, key=lambda r: (r["section_label"] or "", r["subject_name"] or ""))


@router.get("/teachers")
def teachers(section_id: uuid.UUID | None = None, user: User = admin_only, db: Session = Depends(get_db)):
    stmt = (select(Teacher.id, User.full_name, Teacher.employee_no).join(User, User.id == Teacher.user_id)
            .where(Teacher.is_active).order_by(User.full_name))
    if section_id:
        stmt = stmt.where(Teacher.id.in_(select(TeacherAssignment.teacher_id).where(
            TeacherAssignment.section_id == section_id, TeacherAssignment.academic_year_id == current_year(db).id)))
    return [{"id": r[0], "full_name": r[1], "employee_no": r[2]} for r in db.execute(stmt).all()]


@router.get("/students")
def students(section_id: uuid.UUID = Query(...), user: User = staff, db: Session = Depends(get_db)):
    allowed = visible_section_ids(user, db)
    if allowed is not None and section_id not in allowed:
        raise NotFound("Section not found")
    rows = db.execute(select(Student.id, Student.roll_no, Student.full_name).where(
        Student.section_id == section_id, Student.is_active).order_by(Student.roll_no)).all()
    return [{"id": r[0], "roll_no": r[1], "full_name": r[2], "section_id": section_id} for r in rows]


@router.get("/students/search")
def search_students(q: str = Query("", max_length=60), limit: int = Query(15, ge=1, le=50), user: User = admin_only,
                    db: Session = Depends(get_db)):
    stmt = select(Student.id, Student.roll_no, Student.full_name, Student.section_id).where(Student.is_active)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(Student.full_name.ilike(like) | Student.roll_no.ilike(like))
    rows = db.execute(stmt.order_by(Student.full_name).limit(limit)).all()
    labels = section_labels(db, [r[3] for r in rows])
    return [{"id": r[0], "roll_no": r[1], "full_name": r[2], "section_id": r[3], "section_label": labels.get(r[3])}
            for r in rows]


@router.get("/my-children")
def children(user: User = Depends(require_roles("parent")), db: Session = Depends(get_db)):
    ids = parent_child_ids(user, db)
    if not ids:
        return []
    rows = db.execute(select(Student.id, Student.roll_no, Student.full_name, Student.section_id)
                      .where(Student.id.in_(ids)).order_by(Student.full_name)).all()
    labels = section_labels(db, [r[3] for r in rows])
    return [{"student_id": r[0], "roll_no": r[1], "full_name": r[2], "section_id": r[3],
             "section_label": labels.get(r[3])} for r in rows]


@router.get("/admins")
def admins(user: User = admin_only, db: Session = Depends(get_db)):
    """Staff accounts a complaint can be assigned to."""
    rows = db.execute(select(User.id, User.full_name).where(User.role == "admin", User.is_active)
                      .order_by(User.full_name)).all()
    return [{"id": r[0], "full_name": r[1]} for r in rows]
