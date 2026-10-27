import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.access import can_access_student, student_id_for, teacher_id_for
from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import get_current_user, require_roles
from app.modules.ops_common.core_refs import Section, Student, Subject, User
from app.modules.ops_common.scope import current_year_id, get_or_404, not_found, require_section_visible, student_section_id
from app.modules.timetable import service
from app.modules.timetable.models import PeriodDefinition, TimetableSlot
from app.modules.timetable.schemas import (
    PeriodCreate, PeriodOut, PeriodUpdate, SlotCreate, SlotOut, SlotUpdate, WeekOut,
)

router = APIRouter(tags=["Timetable"])
ADMIN = Depends(require_roles("admin"))


# ---------------------------------------------------------------- period definitions
@router.get("/period-definitions", response_model=list[PeriodOut])
def list_periods(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return list(db.scalars(select(PeriodDefinition).order_by(PeriodDefinition.period_no)))


@router.post("/period-definitions", response_model=PeriodOut, status_code=201)
def create_period(payload: PeriodCreate, db: Session = Depends(get_db), user: User = ADMIN):
    if db.scalar(select(PeriodDefinition.id).where(PeriodDefinition.period_no == payload.period_no)) is not None:
        raise AppError(409, "conflict", "This period number already exists")
    service.ensure_period_free(db, payload.start_time, payload.end_time)
    period = PeriodDefinition(**payload.model_dump())
    db.add(period)
    db.commit()
    return period


@router.patch("/period-definitions/{period_id}", response_model=PeriodOut)
def update_period(period_id: uuid.UUID, payload: PeriodUpdate, db: Session = Depends(get_db), user: User = ADMIN):
    period = get_or_404(db, PeriodDefinition, period_id, "Period")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is None:
            raise AppError(422, "validation_error", f"{field} cannot be empty")
        setattr(period, field, value)
    if period.end_time <= period.start_time:
        raise AppError(422, "validation_error", "end_time must be after start_time")
    service.ensure_period_free(db, period.start_time, period.end_time, exclude_id=period.id)
    db.commit()
    return period


@router.delete("/period-definitions/{period_id}", status_code=204)
def delete_period(period_id: uuid.UUID, db: Session = Depends(get_db), user: User = ADMIN):
    period = get_or_404(db, PeriodDefinition, period_id, "Period")
    if db.scalar(select(TimetableSlot.id).where(TimetableSlot.period_id == period.id).limit(1)) is not None:
        raise AppError(409, "conflict", "Lessons are scheduled in this period")
    db.delete(period)
    db.commit()


# ---------------------------------------------------------------- slots
def _slot_out(db: Session, slot_id: uuid.UUID) -> SlotOut:
    return service.to_slot_out(db.execute(service.slot_query().where(TimetableSlot.id == slot_id)).first())


@router.post("/timetable-slots", response_model=SlotOut, status_code=201)
def create_slot(payload: SlotCreate, db: Session = Depends(get_db), user: User = ADMIN):
    get_or_404(db, Section, payload.section_id, "Section")
    get_or_404(db, Subject, payload.subject_id, "Subject")
    year_id = service.year_or_400(db, payload.academic_year_id)
    teacher_id = service.resolve_teacher(db, payload.section_id, payload.subject_id, payload.teacher_id)
    service.validate_slot(
        db, year_id=year_id, section_id=payload.section_id, subject_id=payload.subject_id, teacher_id=teacher_id,
        day_of_week=payload.day_of_week, period_id=payload.period_id,
    )
    slot = TimetableSlot(
        academic_year_id=year_id, section_id=payload.section_id, subject_id=payload.subject_id, teacher_id=teacher_id,
        day_of_week=payload.day_of_week, period_id=payload.period_id, room=payload.room,
    )
    db.add(slot)
    db.commit()
    return _slot_out(db, slot.id)


@router.patch("/timetable-slots/{slot_id}", response_model=SlotOut)
def update_slot(slot_id: uuid.UUID, payload: SlotUpdate, db: Session = Depends(get_db), user: User = ADMIN):
    slot = get_or_404(db, TimetableSlot, slot_id, "Lesson")
    changes = payload.model_dump(exclude_unset=True)
    for field in ("subject_id", "day_of_week", "period_id"):
        if field in changes and changes[field] is None:
            raise AppError(422, "validation_error", f"{field} cannot be empty")
    subject_id = changes.get("subject_id", slot.subject_id)
    teacher_id = changes.get("teacher_id")
    if teacher_id is None:
        # keep the current teacher unless the subject changed (then look up who teaches the new subject)
        teacher_id = slot.teacher_id if subject_id == slot.subject_id else service.resolve_teacher(db, slot.section_id, subject_id, None)
    day = changes.get("day_of_week", slot.day_of_week)
    period_id = changes.get("period_id", slot.period_id)
    service.validate_slot(
        db, year_id=slot.academic_year_id, section_id=slot.section_id, subject_id=subject_id, teacher_id=teacher_id,
        day_of_week=day, period_id=period_id, exclude_id=slot.id,
    )
    slot.subject_id, slot.teacher_id, slot.day_of_week, slot.period_id = subject_id, teacher_id, day, period_id
    if "room" in changes:
        slot.room = changes["room"]
    db.commit()
    return _slot_out(db, slot.id)


@router.delete("/timetable-slots/{slot_id}", status_code=204)
def delete_slot(slot_id: uuid.UUID, db: Session = Depends(get_db), user: User = ADMIN):
    db.delete(get_or_404(db, TimetableSlot, slot_id, "Lesson"))
    db.commit()


# ---------------------------------------------------------------- reading
@router.get("/timetable/sections/{section_id}", response_model=WeekOut)
def section_timetable(
    section_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    require_section_visible(user, db, section_id, "Timetable")
    get_or_404(db, Section, section_id, "Timetable")
    return service.week(db, TimetableSlot.section_id == section_id, TimetableSlot.academic_year_id == current_year_id(db))


@router.get("/timetable/teachers/{teacher_id}", response_model=WeekOut)
def teacher_timetable(
    teacher_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "teacher"))
):
    if user.role == "teacher" and teacher_id_for(user, db) != teacher_id:
        raise AppError(403, "forbidden", "You can only view your own timetable")
    return service.week(db, TimetableSlot.teacher_id == teacher_id, TimetableSlot.academic_year_id == current_year_id(db))


@router.get("/timetable/me", response_model=WeekOut)
def my_timetable(db: Session = Depends(get_db), user: User = Depends(require_roles("teacher", "student"))):
    year = TimetableSlot.academic_year_id == current_year_id(db)
    if user.role == "teacher":
        return service.week(db, TimetableSlot.teacher_id == teacher_id_for(user, db), year)
    return service.week(db, TimetableSlot.section_id == student_section_id(db, student_id_for(user, db)), year)


@router.get("/timetable/students/{student_id}", response_model=WeekOut)
def student_timetable(
    student_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_roles("admin", "parent"))
):
    if not can_access_student(user, student_id, db):
        raise not_found("Student")
    section_id = student_section_id(db, student_id)
    return service.week(db, TimetableSlot.section_id == section_id, TimetableSlot.academic_year_id == current_year_id(db))
