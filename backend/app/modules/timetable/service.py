import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.access import teacher_teaches
from app.core.errors import AppError
from app.modules.ops_common.core_refs import AcademicYear, SchoolClass, Section, Subject, Teacher, User
from app.modules.ops_common.scope import current_year_id, get_or_404, teacher_for_subject
from app.modules.timetable.models import PeriodDefinition, TimetableSlot
from app.modules.timetable.schemas import PeriodOut, SlotOut, WeekOut


def slot_query():
    return (
        select(TimetableSlot, Subject.name, Section.name, SchoolClass.name, User.full_name, PeriodDefinition)
        .join(Subject, Subject.id == TimetableSlot.subject_id)
        .join(Section, Section.id == TimetableSlot.section_id)
        .join(SchoolClass, SchoolClass.id == Section.class_id)
        .join(Teacher, Teacher.id == TimetableSlot.teacher_id)
        .join(User, User.id == Teacher.user_id)
        .join(PeriodDefinition, PeriodDefinition.id == TimetableSlot.period_id)
    )


def to_slot_out(row) -> SlotOut:
    slot, subject_name, section_name, class_name, teacher_name, period = row
    return SlotOut(
        id=slot.id, section_id=slot.section_id, section_name=f"{class_name}-{section_name}", subject_id=slot.subject_id,
        subject_name=subject_name, teacher_id=slot.teacher_id, teacher_name=teacher_name, day_of_week=slot.day_of_week,
        period_id=slot.period_id, period_no=period.period_no, start_time=period.start_time, end_time=period.end_time,
        room=slot.room,
    )


def week(db: Session, *conditions) -> WeekOut:
    rows = db.execute(
        slot_query().where(*conditions).order_by(TimetableSlot.day_of_week, PeriodDefinition.period_no)
    ).all()
    periods = list(db.scalars(select(PeriodDefinition).order_by(PeriodDefinition.period_no)))
    return WeekOut(periods=[PeriodOut.model_validate(p) for p in periods], slots=[to_slot_out(r) for r in rows])


def validate_slot(
    db: Session, *, year_id: uuid.UUID, section_id, subject_id, teacher_id, day_of_week: int, period_id,
    exclude_id: uuid.UUID | None = None,
) -> None:
    period = get_or_404(db, PeriodDefinition, period_id, "Period")
    if period.is_break:
        raise AppError(400, "bad_request", "Lessons cannot be scheduled in a break period")
    if not teacher_teaches(db, teacher_id, section_id, subject_id):
        raise AppError(400, "bad_request", "This teacher is not assigned to teach this subject in this section")
    same_section = select(TimetableSlot.id).where(
        TimetableSlot.academic_year_id == year_id, TimetableSlot.section_id == section_id,
        TimetableSlot.day_of_week == day_of_week, TimetableSlot.period_id == period_id,
    )
    same_teacher = select(TimetableSlot.id).where(
        TimetableSlot.academic_year_id == year_id, TimetableSlot.teacher_id == teacher_id,
        TimetableSlot.day_of_week == day_of_week, TimetableSlot.period_id == period_id,
    )
    if exclude_id is not None:
        same_section = same_section.where(TimetableSlot.id != exclude_id)
        same_teacher = same_teacher.where(TimetableSlot.id != exclude_id)
    if db.scalar(same_section) is not None:
        raise AppError(409, "conflict", "This section already has a lesson in that period")
    if db.scalar(same_teacher) is not None:
        raise AppError(409, "conflict", "This teacher is already teaching another section in that period")


def resolve_teacher(db: Session, section_id, subject_id, teacher_id):
    if teacher_id is not None:
        return teacher_id
    found = teacher_for_subject(db, section_id, subject_id)
    if found is None:
        raise AppError(400, "bad_request", "No teacher is assigned to this subject in this section")
    return found


def year_or_400(db: Session, year_id):
    if year_id is not None:
        get_or_404(db, AcademicYear, year_id, "Academic year")  # 404, not a database error
        return year_id
    year_id = current_year_id(db)
    if year_id is None:
        raise AppError(400, "bad_request", "No current academic year is set")
    return year_id


def ensure_period_free(db: Session, start, end, exclude_id=None) -> None:
    stmt = select(PeriodDefinition.id).where(PeriodDefinition.start_time < end, PeriodDefinition.end_time > start)
    if exclude_id is not None:
        stmt = stmt.where(PeriodDefinition.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise AppError(409, "conflict", "This time overlaps another period")


# ---- PDF data function for Member 1 (docs/API_CONTRACT.md section 5) ----
def get_timetable_data(db: Session, section_id: uuid.UUID) -> dict:
    section_row = db.execute(
        select(Section, SchoolClass.name).join(SchoolClass, SchoolClass.id == Section.class_id).where(Section.id == section_id)
    ).first()
    if section_row is None:
        raise AppError(404, "not_found", "Section not found")
    section, class_name = section_row
    data = week(db, TimetableSlot.section_id == section_id, TimetableSlot.academic_year_id == current_year_id(db))
    return {"section": {"id": section.id, "name": f"{class_name}-{section.name}"}, **data.model_dump()}
