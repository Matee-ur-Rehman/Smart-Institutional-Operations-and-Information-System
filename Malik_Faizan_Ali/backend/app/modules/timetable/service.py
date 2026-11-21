import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.scope import current_year_id, section_labels, subject_names, teacher_names
from app.core.access import teacher_teaches
from app.core.errors import BadRequest, Conflict, NotFound
from app.modules.foundation.models import TeacherAssignment
from app.modules.timetable.models import PeriodDefinition, TimetableSlot
from app.modules.timetable.schemas import PeriodOut, SlotOut

DAYS = [(1, "Monday"), (2, "Tuesday"), (3, "Wednesday"), (4, "Thursday"), (5, "Friday"), (6, "Saturday")]


def slots_out(db: Session, rows: list[TimetableSlot]) -> list[SlotOut]:
    if not rows:
        return []
    sec = section_labels(db, {r.section_id for r in rows})
    sub = subject_names(db, {r.subject_id for r in rows})
    tea = teacher_names(db, {r.teacher_id for r in rows})
    per = {p.id: p for p in db.scalars(select(PeriodDefinition).where(PeriodDefinition.id.in_({r.period_id for r in rows})))}
    return [SlotOut(id=r.id, section_id=r.section_id, section_label=sec.get(r.section_id), subject_id=r.subject_id,
                    subject_name=sub.get(r.subject_id), teacher_id=r.teacher_id, teacher_name=tea.get(r.teacher_id),
                    day_of_week=r.day_of_week, period_id=r.period_id, period_no=per[r.period_id].period_no,
                    start_time=per[r.period_id].start_time, end_time=per[r.period_id].end_time, room=r.room)
            for r in rows]


def all_periods(db: Session) -> list[PeriodOut]:
    return [PeriodOut.model_validate(p) for p in db.scalars(select(PeriodDefinition).order_by(PeriodDefinition.period_no))]


def _order(rows: list[TimetableSlot], db: Session) -> list[TimetableSlot]:
    pno = {p.id: p.period_no for p in db.scalars(select(PeriodDefinition))}
    return sorted(rows, key=lambda r: (r.day_of_week, pno.get(r.period_id, 99)))


def section_timetable(db: Session, section_id: uuid.UUID) -> dict:
    year = current_year_id(db)
    rows = list(db.scalars(select(TimetableSlot).where(TimetableSlot.section_id == section_id,
                                                        TimetableSlot.academic_year_id == year)))
    return {"section_id": section_id, "section_label": section_labels(db, [section_id]).get(section_id),
            "academic_year_id": year, "days": [{"day": d, "name": n} for d, n in DAYS],
            "periods": all_periods(db), "slots": slots_out(db, _order(rows, db))}


def teacher_timetable(db: Session, teacher_id: uuid.UUID) -> dict:
    year = current_year_id(db)
    rows = list(db.scalars(select(TimetableSlot).where(TimetableSlot.teacher_id == teacher_id,
                                                        TimetableSlot.academic_year_id == year)))
    return {"teacher_id": teacher_id, "teacher_name": teacher_names(db, [teacher_id]).get(teacher_id),
            "academic_year_id": year, "days": [{"day": d, "name": n} for d, n in DAYS],
            "periods": all_periods(db), "slots": slots_out(db, _order(rows, db))}


def get_timetable_data(db: Session, section_id: uuid.UUID) -> dict:
    """Plain-dict data for Member 1's PDF engine (API_CONTRACT.md section 5)."""
    return section_timetable(db, section_id)


def resolve_teacher(db: Session, section_id, subject_id, teacher_id) -> uuid.UUID:
    """The teacher must teach that subject in that section (teacher_assignments)."""
    if teacher_id is None:
        teacher_id = db.scalar(select(TeacherAssignment.teacher_id).where(
            TeacherAssignment.section_id == section_id, TeacherAssignment.subject_id == subject_id,
            TeacherAssignment.academic_year_id == current_year_id(db)))
        if teacher_id is None:
            raise BadRequest("No teacher is assigned to this subject in this section", code="no_teacher_assigned")
        return teacher_id
    if not teacher_teaches(db, teacher_id, section_id, subject_id):
        raise BadRequest("This teacher is not assigned to teach this subject in this section", code="teacher_not_assigned")
    return teacher_id


def check_slot(db: Session, year_id, section_id, subject_id, teacher_id, day, period_id, exclude_id=None) -> uuid.UUID:
    period = db.get(PeriodDefinition, period_id)
    if period is None:
        raise NotFound("Period not found")
    if period.is_break:
        raise BadRequest("Lessons cannot be scheduled in a break period", code="break_period")
    teacher_id = resolve_teacher(db, section_id, subject_id, teacher_id)
    taken = db.scalar(select(TimetableSlot).where(
        TimetableSlot.academic_year_id == year_id, TimetableSlot.section_id == section_id,
        TimetableSlot.day_of_week == day, TimetableSlot.period_id == period_id))
    if taken is not None and taken.id != exclude_id:
        raise Conflict("This section already has a lesson in that period", code="slot_taken")
    busy = db.scalar(select(TimetableSlot).where(
        TimetableSlot.academic_year_id == year_id, TimetableSlot.teacher_id == teacher_id,
        TimetableSlot.day_of_week == day, TimetableSlot.period_id == period_id, TimetableSlot.section_id != section_id))
    if busy is not None and busy.id != exclude_id:
        raise Conflict("This teacher is already teaching another section in that period", code="teacher_busy")
    return teacher_id
