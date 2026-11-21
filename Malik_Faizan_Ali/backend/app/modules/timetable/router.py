import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.scope import (
    current_year_id, own_student, require_visible_section, section_of_student,
)
from app.core.access import can_access_student, teacher_id_for
from app.core.database import get_db
from app.core.errors import BadRequest, Conflict, NotFound, ValidationFailed, field_error
from app.core.security import get_current_user, require_roles
from app.modules.foundation.models import Section, Subject, User
from app.modules.timetable import service
from app.modules.timetable.models import PeriodDefinition, TimetableSlot
from app.modules.timetable.schemas import PeriodCreate, PeriodOut, PeriodUpdate, SlotCreate, SlotOut, SlotUpdate

router = APIRouter(tags=["Timetable"])
admin_only = Depends(require_roles("admin"))


# ============================================================ periods
def _check_period_overlap(db: Session, start, end, exclude_id=None):
    for p in db.scalars(select(PeriodDefinition)):
        if p.id != exclude_id and start < p.end_time and p.start_time < end:
            raise Conflict(f"Overlaps with period {p.period_no} ({p.label})", code="period_overlap")


@router.post("/period-definitions", response_model=PeriodOut, status_code=201)
def create_period(body: PeriodCreate, user: User = admin_only, db: Session = Depends(get_db)):
    if db.scalar(select(PeriodDefinition.id).where(PeriodDefinition.period_no == body.period_no)):
        raise Conflict("A period with this number already exists", code="duplicate_period")
    _check_period_overlap(db, body.start_time, body.end_time)
    p = PeriodDefinition(**body.model_dump())
    db.add(p)
    db.commit()
    return p


@router.get("/period-definitions", response_model=list[PeriodOut])
def list_periods(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.all_periods(db)


def _period(db: Session, pid: uuid.UUID) -> PeriodDefinition:
    p = db.get(PeriodDefinition, pid)
    if p is None:
        raise NotFound("Period not found")
    return p


@router.get("/period-definitions/{period_id}", response_model=PeriodOut)
def get_period(period_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _period(db, period_id)


@router.patch("/period-definitions/{period_id}", response_model=PeriodOut)
def update_period(period_id: uuid.UUID, body: PeriodUpdate, user: User = admin_only, db: Session = Depends(get_db)):
    p = _period(db, period_id)
    data = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    new_start, new_end = data.get("start_time", p.start_time), data.get("end_time", p.end_time)
    if new_end <= new_start:
        raise ValidationFailed(errors=[field_error("end_time", "end_time must be after start_time")])
    if "period_no" in data and data["period_no"] != p.period_no and db.scalar(
            select(PeriodDefinition.id).where(PeriodDefinition.period_no == data["period_no"])):
        raise Conflict("A period with this number already exists", code="duplicate_period")
    if data.get("is_break") and db.scalar(select(TimetableSlot.id).where(TimetableSlot.period_id == p.id).limit(1)):
        raise Conflict("Lessons are scheduled in this period; it cannot become a break", code="in_use")
    _check_period_overlap(db, new_start, new_end, p.id)
    for k, v in data.items():
        setattr(p, k, v)
    db.commit()
    return p


@router.delete("/period-definitions/{period_id}", status_code=204)
def delete_period(period_id: uuid.UUID, user: User = admin_only, db: Session = Depends(get_db)):
    p = _period(db, period_id)
    if db.scalar(select(TimetableSlot.id).where(TimetableSlot.period_id == p.id).limit(1)):
        raise Conflict("Lessons are scheduled in this period and it cannot be deleted", code="in_use")
    db.delete(p)
    db.commit()


# ============================================================ slots
@router.post("/timetable-slots", response_model=SlotOut, status_code=201)
def create_slot(body: SlotCreate, user: User = admin_only, db: Session = Depends(get_db)):
    errors = []
    if db.get(Section, body.section_id) is None:
        errors.append(field_error("section_id", "Section does not exist"))
    if db.get(Subject, body.subject_id) is None:
        errors.append(field_error("subject_id", "Subject does not exist"))
    if errors:
        raise ValidationFailed(errors=errors)
    year = current_year_id(db)
    teacher_id = service.check_slot(db, year, body.section_id, body.subject_id, body.teacher_id, body.day_of_week, body.period_id)
    slot = TimetableSlot(academic_year_id=year, section_id=body.section_id, subject_id=body.subject_id,
                         teacher_id=teacher_id, day_of_week=body.day_of_week, period_id=body.period_id, room=body.room)
    db.add(slot)
    db.commit()
    return service.slots_out(db, [slot])[0]


def _slot(db: Session, sid: uuid.UUID) -> TimetableSlot:
    s = db.get(TimetableSlot, sid)
    if s is None:
        raise NotFound("Timetable slot not found")
    return s


@router.patch("/timetable-slots/{slot_id}", response_model=SlotOut)
def update_slot(slot_id: uuid.UUID, body: SlotUpdate, user: User = admin_only, db: Session = Depends(get_db)):
    s = _slot(db, slot_id)
    data = body.model_dump(exclude_unset=True)
    subject_id = data.get("subject_id") or s.subject_id
    day = data.get("day_of_week") or s.day_of_week
    period_id = data.get("period_id") or s.period_id
    # changing the subject without naming a teacher re-derives the teacher from teacher_assignments
    teacher_req = data.get("teacher_id") or (s.teacher_id if subject_id == s.subject_id else None)
    teacher_id = service.check_slot(db, s.academic_year_id, s.section_id, subject_id, teacher_req, day, period_id, s.id)
    s.subject_id, s.teacher_id, s.day_of_week, s.period_id = subject_id, teacher_id, day, period_id
    if "room" in data:
        s.room = data["room"]
    db.commit()
    return service.slots_out(db, [s])[0]


@router.delete("/timetable-slots/{slot_id}", status_code=204)
def delete_slot(slot_id: uuid.UUID, user: User = admin_only, db: Session = Depends(get_db)):
    db.delete(_slot(db, slot_id))
    db.commit()


# ============================================================ views
@router.get("/timetable/sections/{section_id}")
def timetable_of_section(section_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if db.get(Section, section_id) is None:
        raise NotFound("Section not found")
    if user.role != "teacher":  # teachers may view any section's (non-private) timetable
        require_visible_section(user, db, section_id)
    return service.section_timetable(db, section_id)


@router.get("/timetable/teachers/{teacher_id}")
def timetable_of_teacher(teacher_id: uuid.UUID, user: User = Depends(require_roles("admin", "teacher")),
                         db: Session = Depends(get_db)):
    if user.role == "teacher" and teacher_id_for(user, db) != teacher_id:
        raise NotFound("Teacher not found")
    if service.teacher_names(db, [teacher_id]).get(teacher_id) is None:
        raise NotFound("Teacher not found")
    return service.teacher_timetable(db, teacher_id)


@router.get("/timetable/me")
def my_timetable(user: User = Depends(require_roles("teacher", "student")), db: Session = Depends(get_db)):
    if user.role == "teacher":
        return service.teacher_timetable(db, teacher_id_for(user, db))
    st = own_student(user, db)
    if st is None:
        raise NotFound("Student profile not found")
    return service.section_timetable(db, st.section_id)


@router.get("/timetable/students/{student_id}")
def timetable_of_student(student_id: uuid.UUID, user: User = Depends(require_roles("admin", "parent")),
                         db: Session = Depends(get_db)):
    section_id = section_of_student(db, student_id)
    if section_id is None or not can_access_student(user, student_id, db):
        raise NotFound("Student not found")
    return service.section_timetable(db, section_id)
