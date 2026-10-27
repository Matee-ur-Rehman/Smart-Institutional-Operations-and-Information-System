import uuid
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.access import teacher_id_for, teacher_teaches
from app.core.errors import AppError
from app.modules.exams.models import Exam, ExamSchedule, GradeScale, Mark
from app.modules.exams.schemas import GradeBand, MarkEntry, ScheduleOut
from app.modules.ops_common.core_refs import SchoolClass, Section, Student, Subject, User
from app.modules.ops_common.scope import not_found, user_section_ids


def get_exam_visible(db: Session, user: User, exam_id: uuid.UUID) -> Exam:
    exam = db.get(Exam, exam_id)
    if exam is None or (user.role != "admin" and exam.status == "draft"):
        raise not_found("Exam")
    return exam


def schedule_query():
    return (
        select(ExamSchedule, Subject.name, Section.name, SchoolClass.name)
        .join(Subject, Subject.id == ExamSchedule.subject_id)
        .join(Section, Section.id == ExamSchedule.section_id)
        .join(SchoolClass, SchoolClass.id == Section.class_id)
    )


def schedule_to_out(row) -> ScheduleOut:
    schedule, subject_name, section_name, class_name = row
    return ScheduleOut(
        id=schedule.id, exam_id=schedule.exam_id, section_id=schedule.section_id,
        section_name=f"{class_name}-{section_name}", subject_id=schedule.subject_id, subject_name=subject_name,
        exam_date=schedule.exam_date, start_time=schedule.start_time, end_time=schedule.end_time,
        room=schedule.room, total_marks=schedule.total_marks, passing_marks=schedule.passing_marks,
    )


def schedule_scope(user: User, db: Session) -> list:
    sections = user_section_ids(user, db)
    return [] if sections is None else [ExamSchedule.section_id.in_(sections)]


def ensure_no_overlap(db: Session, exam_id, section_id, exam_date, start, end, exclude_id=None) -> None:
    stmt = select(ExamSchedule.id).where(
        ExamSchedule.exam_id == exam_id,
        ExamSchedule.section_id == section_id,
        ExamSchedule.exam_date == exam_date,
        ExamSchedule.start_time < end,
        ExamSchedule.end_time > start,
    )
    if exclude_id is not None:
        stmt = stmt.where(ExamSchedule.id != exclude_id)
    if db.scalar(stmt) is not None:
        raise AppError(409, "conflict", "This section already has a paper at an overlapping time")


def delete_exam_children(db: Session, exam_id: uuid.UUID) -> None:
    ids = list(db.scalars(select(ExamSchedule.id).where(ExamSchedule.exam_id == exam_id)))
    if ids:
        db.execute(delete(Mark).where(Mark.exam_schedule_id.in_(ids)))
        db.execute(delete(ExamSchedule).where(ExamSchedule.id.in_(ids)))


def ensure_can_enter_marks(db: Session, user: User, schedule: ExamSchedule) -> Exam:
    exam = db.get(Exam, schedule.exam_id)
    if user.role == "teacher":
        if not teacher_teaches(db, teacher_id_for(user, db), schedule.section_id, schedule.subject_id):
            raise AppError(403, "forbidden", "You do not teach this subject in this section")
    if exam.status == "results_published":
        raise AppError(409, "conflict", "Results are published, so marks are locked")
    return exam


def upsert_marks(db: Session, user: User, schedule: ExamSchedule, entries: list[MarkEntry]) -> int:
    student_ids = [e.student_id for e in entries]
    if len(set(student_ids)) != len(student_ids):
        raise AppError(400, "bad_request", "The same student appears more than once")
    valid = set(
        db.scalars(
            select(Student.id).where(
                Student.id.in_(student_ids), Student.section_id == schedule.section_id, Student.is_active.is_(True)
            )
        )
    )
    outsiders = [str(sid) for sid in student_ids if sid not in valid]
    if outsiders:
        raise AppError(400, "bad_request", "Some students are not in this section", [{"field": "student_id", "message": s} for s in outsiders])
    too_high = [e for e in entries if e.marks_obtained is not None and Decimal(e.marks_obtained) > schedule.total_marks]
    if too_high:
        raise AppError(
            400, "bad_request", f"Marks cannot exceed the total of {schedule.total_marks}",
            [{"field": "marks_obtained", "message": str(e.student_id)} for e in too_high],
        )
    existing = {m.student_id: m for m in db.scalars(select(Mark).where(Mark.exam_schedule_id == schedule.id))}
    for entry in entries:
        mark = existing.get(entry.student_id)
        if mark is None:
            mark = Mark(exam_schedule_id=schedule.id, student_id=entry.student_id, entered_by=user.id)
            db.add(mark)
        mark.marks_obtained = entry.marks_obtained
        mark.is_absent = entry.is_absent
        mark.remarks = entry.remarks
        mark.entered_by = user.id
    db.flush()
    return len(entries)


def validate_bands(bands: list[GradeBand]) -> None:
    grades = [b.grade.strip().upper() for b in bands]
    if len(set(grades)) != len(grades):
        raise AppError(422, "validation_error", "Each grade may appear only once")
    ordered = sorted(bands, key=lambda b: b.min_percentage)
    for previous, current in zip(ordered, ordered[1:]):
        if current.min_percentage <= previous.max_percentage:
            raise AppError(422, "validation_error", f"Grade bands {previous.grade} and {current.grade} overlap")


def replace_scale(db: Session, bands: list[GradeBand]) -> list[GradeScale]:
    validate_bands(bands)
    db.execute(delete(GradeScale))
    rows = [
        GradeScale(
            grade=b.grade.strip().upper(), min_percentage=b.min_percentage, max_percentage=b.max_percentage,
            gpa_points=b.gpa_points, remark=b.remark, is_pass=b.is_pass,
        )
        for b in bands
    ]
    db.add_all(rows)
    db.flush()
    return rows
