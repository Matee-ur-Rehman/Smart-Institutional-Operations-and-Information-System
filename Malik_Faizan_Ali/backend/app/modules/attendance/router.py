import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.scope import parent_user_ids_of_student, section_labels, teacher_section_ids, teacher_teaches_section
from app.common.timeutil import school_today
from app.core.access import can_access_student, teacher_id_for
from app.core.database import get_db
from app.core.errors import BadRequest, Forbidden, NotFound, ValidationFailed, field_error
from app.core.security import get_current_user, require_roles
from app.modules.attendance import service
from app.modules.attendance.models import Attendance
from app.modules.attendance.schemas import AttendanceBulk, RecordOut, SheetOut, SheetRow, StudentAttendanceOut
from app.modules.foundation.models import Section, Student, User
from app.modules.leave.models import LeaveRequest
from app.modules.notifications.service import notify_users

router = APIRouter(prefix="/attendance", tags=["Attendance"])
staff = Depends(require_roles("admin", "teacher"))
TEACHER_EDIT_DAYS = 7


def _section(db: Session, user: User, section_id: uuid.UUID) -> Section:
    sec = db.get(Section, section_id)
    if sec is None or (user.role == "teacher" and not teacher_teaches_section(db, teacher_id_for(user, db), section_id)):
        raise NotFound("Section not found")
    return sec


def _editable(db: Session, user: User, section_id: uuid.UUID, d: date) -> bool:
    today = school_today()
    if d > today or not service.is_school_day(d) or service.is_holiday(db, d, section_id):
        return False
    return user.role == "admin" or d >= today - timedelta(days=TEACHER_EDIT_DAYS)


def _sheet(db: Session, user: User, sec: Section, d: date) -> SheetOut:
    students = list(db.execute(select(Student.id, Student.roll_no, Student.full_name)
                               .where(Student.section_id == sec.id, Student.is_active)
                               .order_by(Student.roll_no)))
    recs = {a.student_id: a for a in db.scalars(select(Attendance).where(
        Attendance.section_id == sec.id, Attendance.attendance_date == d))}
    on_leave = set(db.scalars(select(LeaveRequest.student_id).where(
        LeaveRequest.status == "approved", LeaveRequest.from_date <= d, LeaveRequest.to_date >= d,
        LeaveRequest.student_id.in_([s.id for s in students]))))
    rows = [SheetRow(student_id=s.id, roll_no=s.roll_no, full_name=s.full_name,
                     status=recs[s.id].status if s.id in recs else None,
                     remarks=recs[s.id].remarks if s.id in recs else None,
                     on_approved_leave=s.id in on_leave) for s in students]
    counts = {k: sum(1 for r in rows if r.status == k) for k in ("present", "absent", "late", "leave")}
    return SheetOut(section_id=sec.id, section_label=section_labels(db, [sec.id]).get(sec.id), date=d,
                    editable=_editable(db, user, sec.id, d), marked=sum(counts.values()), total=len(rows),
                    counts=counts, rows=rows)


@router.get("/sections/{section_id}", response_model=SheetOut)
def get_sheet(section_id: uuid.UUID, on: date | None = Query(None, alias="date"), user: User = staff,
              db: Session = Depends(get_db)):
    return _sheet(db, user, _section(db, user, section_id), on or school_today())


@router.put("/sections/{section_id}", response_model=SheetOut)
def save_sheet(section_id: uuid.UUID, body: AttendanceBulk, on: date | None = Query(None, alias="date"),
               user: User = staff, db: Session = Depends(get_db)):
    sec = _section(db, user, section_id)
    d = on or school_today()
    today = school_today()
    if d > today:
        raise BadRequest("Attendance cannot be marked for a future date", code="future_date")
    if not service.is_school_day(d):
        raise BadRequest("Sunday is not a school day", code="not_school_day")
    if service.is_holiday(db, d, sec.id):
        raise BadRequest("This date is a school holiday", code="holiday")
    if user.role == "teacher" and d < today - timedelta(days=TEACHER_EDIT_DAYS):
        raise Forbidden(f"Teachers can only change the last {TEACHER_EDIT_DAYS} days; ask an admin to correct older dates")

    in_section = {s.id: s for s in db.scalars(select(Student).where(Student.section_id == sec.id, Student.is_active))}
    errors, seen = [], set()
    for i, e in enumerate(body.entries):
        if e.student_id in seen:
            errors.append(field_error(f"entries.{i}.student_id", "Student appears more than once"))
        seen.add(e.student_id)
        if e.student_id not in in_section:
            errors.append(field_error(f"entries.{i}.student_id", "Student is not in this section"))
    if errors:
        raise ValidationFailed(errors=errors)

    existing = {a.student_id: a for a in db.scalars(select(Attendance).where(
        Attendance.section_id == sec.id, Attendance.attendance_date == d))}
    for e in body.entries:
        a = existing.get(e.student_id)
        was_absent = a is not None and a.status == "absent"
        if a is None:
            a = Attendance(student_id=e.student_id, section_id=sec.id, attendance_date=d, status=e.status, marked_by=user.id)
            db.add(a)
            db.flush()
        a.status, a.remarks, a.marked_by = e.status, e.remarks, user.id
        if e.status == "absent" and not was_absent and d == today:
            st = in_section[e.student_id]
            notify_users(db, parent_user_ids_of_student(db, st.id), "Absent today",
                         f"{st.full_name} was marked absent on {d.strftime('%d %b %Y')}.", "attendance", "student", st.id)
    db.commit()
    return _sheet(db, user, sec, d)


def _range(from_date: date | None, to_date: date | None) -> tuple[date, date]:
    today = school_today()
    end = to_date or today
    start = from_date or end.replace(day=1)
    if start > end:
        raise ValidationFailed(errors=[field_error("from_date", "from_date cannot be after to_date")])
    if (end - start).days > 366:
        raise ValidationFailed(errors=[field_error("from_date", "The range cannot be longer than one year")])
    return start, end


def _student_report(db: Session, st: Student, start: date, end: date) -> StudentAttendanceOut:
    rows = list(db.scalars(select(Attendance).where(
        Attendance.student_id == st.id, Attendance.attendance_date.between(start, end)).order_by(Attendance.attendance_date)))
    return StudentAttendanceOut(
        student_id=st.id, student_name=st.full_name, roll_no=st.roll_no,
        section_label=section_labels(db, [st.section_id]).get(st.section_id), from_date=start, to_date=end,
        summary=service.summarize(r.status for r in rows),
        records=[RecordOut(date=r.attendance_date, status=r.status, remarks=r.remarks) for r in rows])


@router.get("/students/{student_id}", response_model=StudentAttendanceOut)
def student_attendance(student_id: uuid.UUID, from_date: date | None = None, to_date: date | None = None,
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    st = db.get(Student, student_id)
    if st is None or not can_access_student(user, student_id, db):
        raise NotFound("Student not found")
    return _student_report(db, st, *_range(from_date, to_date))


@router.get("/me", response_model=StudentAttendanceOut)
def my_attendance(from_date: date | None = None, to_date: date | None = None,
                  user: User = Depends(require_roles("student")), db: Session = Depends(get_db)):
    st = db.scalar(select(Student).where(Student.user_id == user.id, Student.is_active))
    if st is None:
        raise NotFound("Student profile not found")
    return _student_report(db, st, *_range(from_date, to_date))


@router.get("/sections/{section_id}/summary")
def section_summary(section_id: uuid.UUID, from_date: date | None = None, to_date: date | None = None,
                    user: User = staff, db: Session = Depends(get_db)):
    sec = _section(db, user, section_id)
    start, end = _range(from_date, to_date)
    students = list(db.execute(select(Student.id, Student.roll_no, Student.full_name)
                               .where(Student.section_id == sec.id, Student.is_active).order_by(Student.roll_no)))
    by_student: dict[uuid.UUID, list[str]] = {s.id: [] for s in students}
    for sid, status in db.execute(select(Attendance.student_id, Attendance.status).where(
            Attendance.student_id.in_(list(by_student)), Attendance.attendance_date.between(start, end))):
        by_student[sid].append(status)
    out = []
    for s in students:
        sm = service.summarize(by_student[s.id])
        out.append({"student_id": s.id, "roll_no": s.roll_no, "full_name": s.full_name, "summary": sm,
                    "low_attendance": sm.percentage is not None and sm.percentage < service.LOW_ATTENDANCE_THRESHOLD})
    pcts = [r["summary"].percentage for r in out if r["summary"].percentage is not None]
    return {"section_id": sec.id, "section_label": section_labels(db, [sec.id]).get(sec.id), "from_date": start,
            "to_date": end, "threshold": service.LOW_ATTENDANCE_THRESHOLD,
            "average_percentage": round(sum(pcts) / len(pcts), 2) if pcts else None,
            "low_attendance_count": sum(1 for r in out if r["low_attendance"]), "students": out}


@router.get("/overview")
def overview(on: date | None = Query(None, alias="date"), user: User = staff, db: Session = Depends(get_db)):
    """Per-section marking status for one day (dashboard card: which sections have not marked yet)."""
    d = on or school_today()
    stmt = select(Section.id)
    if user.role == "teacher":
        ids = teacher_section_ids(db, teacher_id_for(user, db))
        stmt = stmt.where(Section.id.in_(ids)) if ids else stmt.where(False)
    section_ids = list(db.scalars(stmt))
    labels = section_labels(db, section_ids)
    totals = dict(db.execute(select(Student.section_id, func.count()).where(
        Student.section_id.in_(section_ids), Student.is_active).group_by(Student.section_id)).all())
    counts: dict[uuid.UUID, dict[str, int]] = {}
    for sid, status, n in db.execute(select(Attendance.section_id, Attendance.status, func.count()).where(
            Attendance.section_id.in_(section_ids), Attendance.attendance_date == d).group_by(Attendance.section_id, Attendance.status)):
        counts.setdefault(sid, {})[status] = n
    items = []
    for sid in sorted(section_ids, key=lambda x: labels.get(x, "")):
        c = counts.get(sid, {})
        items.append({"section_id": sid, "section_label": labels.get(sid), "students": totals.get(sid, 0),
                      "marked": sum(c.values()), "present": c.get("present", 0), "absent": c.get("absent", 0),
                      "late": c.get("late", 0), "leave": c.get("leave", 0),
                      "is_marked": sum(c.values()) > 0})
    return {"date": d, "school_day": service.is_school_day(d), "sections": items,
            "unmarked_sections": sum(1 for i in items if not i["is_marked"] and i["students"])}
