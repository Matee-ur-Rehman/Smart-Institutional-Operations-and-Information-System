import uuid
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.access import can_access_student
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import get_current_user, require_roles
from app.modules.exams import results as results_service
from app.modules.exams import service
from app.modules.exams.models import Exam, ExamSchedule, GradeScale, Mark
from app.modules.exams.results import StudentExamResult, StudentResultsOut
from app.modules.exams.schemas import (
    ExamCreate, ExamOut, ExamUpdate, GradeBandOut, GradeScaleIn, MarkSheetOut, MarkSheetRow, MarksBulkIn,
    ScheduleCreate, ScheduleOut, ScheduleUpdate,
)
from app.modules.notifications.push import dispatch_queued_pushes
from app.modules.notifications.service import notify_users, section_recipient_ids
from app.modules.ops_common.core_refs import AcademicYear, Section, Student, Subject, User
from app.modules.ops_common.pagination import Page, PageParams, page_of, paginate
from app.modules.ops_common.scope import current_year_id, get_or_404, not_found, require_section_visible

router = APIRouter(tags=["Exams, Marks & Results"])
ADMIN = Depends(require_roles("admin"))
STAFF = Depends(require_roles("admin", "teacher"))


# ---------------------------------------------------------------- exams
@router.post("/exams", response_model=ExamOut, status_code=201)
def create_exam(payload: ExamCreate, db: Session = Depends(get_db), user: User = ADMIN):
    if payload.academic_year_id is not None:
        get_or_404(db, AcademicYear, payload.academic_year_id, "Academic year")
    year_id = payload.academic_year_id or current_year_id(db)
    if year_id is None:
        raise AppError(400, "bad_request", "No current academic year is set")
    exam = Exam(
        name=payload.name, exam_type=payload.exam_type, academic_year_id=year_id,
        start_date=payload.start_date, end_date=payload.end_date, status=payload.status,
    )
    db.add(exam)
    db.commit()
    return exam


@router.get("/exams", response_model=Page[ExamOut])
def list_exams(
    status: str | None = Query(None, pattern="^(draft|scheduled|ongoing|completed|results_published)$"),
    exam_type: str | None = Query(None, pattern="^(monthly|midterm|final|other)$"),
    academic_year_id: uuid.UUID | None = None,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Exam)
    if user.role != "admin":
        stmt = stmt.where(Exam.status != "draft")
    if status:
        stmt = stmt.where(Exam.status == status)
    if exam_type:
        stmt = stmt.where(Exam.exam_type == exam_type)
    if academic_year_id:
        stmt = stmt.where(Exam.academic_year_id == academic_year_id)
    rows, total = paginate(db, stmt.order_by(Exam.start_date.desc()), params)
    return page_of(rows, total, params)


@router.get("/exams/{exam_id}", response_model=ExamOut)
def get_exam(exam_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return service.get_exam_visible(db, user, exam_id)


@router.patch("/exams/{exam_id}", response_model=ExamOut)
def update_exam(exam_id: uuid.UUID, payload: ExamUpdate, db: Session = Depends(get_db), user: User = ADMIN):
    exam = get_or_404(db, Exam, exam_id, "Exam")
    changes = payload.model_dump(exclude_unset=True)
    if exam.status == "results_published" and "status" in changes:
        # Without this guard an admin could silently un-publish results and unlock the marks again.
        raise AppError(409, "conflict", "Results are published, so the exam status can no longer be changed")
    for field, value in changes.items():
        if value is None:
            raise AppError(422, "validation_error", f"{field} cannot be empty")
        setattr(exam, field, value)
    if exam.end_date < exam.start_date:
        raise AppError(422, "validation_error", "end_date cannot be before start_date")
    db.commit()
    return exam


@router.delete("/exams/{exam_id}", status_code=204)
def delete_exam(exam_id: uuid.UUID, db: Session = Depends(get_db), user: User = ADMIN):
    exam = get_or_404(db, Exam, exam_id, "Exam")
    if exam.status != "draft":
        raise AppError(409, "conflict", "Only draft exams can be deleted")
    service.delete_exam_children(db, exam.id)
    db.delete(exam)
    db.commit()


@router.post("/exams/{exam_id}/publish-results", response_model=ExamOut)
def publish_results(
    exam_id: uuid.UUID, background: BackgroundTasks, db: Session = Depends(get_db), user: User = ADMIN
):
    exam = get_or_404(db, Exam, exam_id, "Exam")
    if exam.status == "results_published":
        raise AppError(409, "conflict", "Results are already published")
    section_ids = list(db.scalars(select(ExamSchedule.section_id).where(ExamSchedule.exam_id == exam.id).distinct()))
    if not section_ids:
        raise AppError(400, "bad_request", "This exam has no papers scheduled, so there is nothing to publish")
    exam.status = "results_published"
    recipients: set[uuid.UUID] = set()
    for section_id in section_ids:  # one set, so a parent with children in two sections is notified once
        recipients |= section_recipient_ids(db, section_id=section_id)
    notify_users(
        db, recipients, title=f"Results published: {exam.name}",
        body="You can now view the results in the app.", type="marks",
        reference_type="exam", reference_id=exam.id,
    )
    db.commit()
    if settings.fcm_enabled:
        background.add_task(dispatch_queued_pushes)
    return exam


# ---------------------------------------------------------------- schedules
@router.post("/exams/{exam_id}/schedules", response_model=ScheduleOut, status_code=201)
def create_schedule(exam_id: uuid.UUID, payload: ScheduleCreate, db: Session = Depends(get_db), user: User = ADMIN):
    exam = get_or_404(db, Exam, exam_id, "Exam")
    if exam.status == "results_published":
        raise AppError(409, "conflict", "Results are published; this exam can no longer be changed")
    get_or_404(db, Section, payload.section_id, "Section")
    get_or_404(db, Subject, payload.subject_id, "Subject")
    if not (exam.start_date <= payload.exam_date <= exam.end_date):
        raise AppError(400, "bad_request", "exam_date must fall within the exam's start and end dates")
    duplicate = db.scalar(
        select(ExamSchedule.id).where(
            ExamSchedule.exam_id == exam.id,
            ExamSchedule.section_id == payload.section_id,
            ExamSchedule.subject_id == payload.subject_id,
        )
    )
    if duplicate is not None:
        raise AppError(409, "conflict", "This subject already has a paper for this section in this exam")
    service.ensure_no_overlap(db, exam.id, payload.section_id, payload.exam_date, payload.start_time, payload.end_time)
    schedule = ExamSchedule(exam_id=exam.id, **payload.model_dump())
    db.add(schedule)
    db.commit()
    return service.schedule_to_out(db.execute(service.schedule_query().where(ExamSchedule.id == schedule.id)).first())


@router.get("/exams/{exam_id}/schedules", response_model=list[ScheduleOut])
def list_schedules(
    exam_id: uuid.UUID,
    section_id: uuid.UUID | None = None,
    subject_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    service.get_exam_visible(db, user, exam_id)
    stmt = service.schedule_query().where(ExamSchedule.exam_id == exam_id, *service.schedule_scope(user, db))
    if section_id:
        stmt = stmt.where(ExamSchedule.section_id == section_id)
    if subject_id:
        stmt = stmt.where(ExamSchedule.subject_id == subject_id)
    rows = db.execute(stmt.order_by(ExamSchedule.exam_date, ExamSchedule.start_time)).all()
    return [service.schedule_to_out(r) for r in rows]


@router.patch("/exam-schedules/{schedule_id}", response_model=ScheduleOut)
def update_schedule(schedule_id: uuid.UUID, payload: ScheduleUpdate, db: Session = Depends(get_db), user: User = ADMIN):
    schedule = get_or_404(db, ExamSchedule, schedule_id, "Paper")
    exam = db.get(Exam, schedule.exam_id)
    if exam.status == "results_published":
        raise AppError(409, "conflict", "Results are published; this exam can no longer be changed")
    changes = payload.model_dump(exclude_unset=True)
    for field in ("exam_date", "start_time", "end_time", "total_marks", "passing_marks"):
        if field in changes and changes[field] is None:
            raise AppError(422, "validation_error", f"{field} cannot be empty")
    for field, value in changes.items():
        setattr(schedule, field, value)
    if schedule.end_time <= schedule.start_time:
        raise AppError(422, "validation_error", "end_time must be after start_time")
    if schedule.passing_marks > schedule.total_marks:
        raise AppError(422, "validation_error", "passing_marks cannot exceed total_marks")
    if not (exam.start_date <= schedule.exam_date <= exam.end_date):
        raise AppError(400, "bad_request", "exam_date must fall within the exam's start and end dates")
    highest = db.scalar(select(func.max(Mark.marks_obtained)).where(Mark.exam_schedule_id == schedule.id))
    if highest is not None and highest > schedule.total_marks:
        raise AppError(409, "conflict", "Some entered marks are higher than the new total marks")
    service.ensure_no_overlap(
        db, schedule.exam_id, schedule.section_id, schedule.exam_date, schedule.start_time, schedule.end_time,
        exclude_id=schedule.id,
    )
    db.commit()
    return service.schedule_to_out(db.execute(service.schedule_query().where(ExamSchedule.id == schedule.id)).first())


@router.delete("/exam-schedules/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: uuid.UUID, db: Session = Depends(get_db), user: User = ADMIN):
    schedule = get_or_404(db, ExamSchedule, schedule_id, "Paper")
    if db.scalar(select(Mark.id).where(Mark.exam_schedule_id == schedule.id).limit(1)) is not None:
        raise AppError(409, "conflict", "Marks have already been entered for this paper")
    db.delete(schedule)
    db.commit()


# ---------------------------------------------------------------- marks
@router.get("/exam-schedules/{schedule_id}/marks", response_model=MarkSheetOut)
def get_mark_sheet(schedule_id: uuid.UUID, db: Session = Depends(get_db), user: User = STAFF):
    schedule = get_or_404(db, ExamSchedule, schedule_id, "Paper")
    exam = db.get(Exam, schedule.exam_id)
    if user.role == "teacher":
        from app.core.access import teacher_id_for, teacher_teaches

        if not teacher_teaches(db, teacher_id_for(user, db), schedule.section_id, schedule.subject_id):
            raise AppError(403, "forbidden", "You do not teach this subject in this section")
    students = list(
        db.scalars(
            select(Student).where(Student.section_id == schedule.section_id, Student.is_active.is_(True)).order_by(Student.roll_no)
        )
    )
    marks = {m.student_id: m for m in db.scalars(select(Mark).where(Mark.exam_schedule_id == schedule.id))}
    rows = [
        MarkSheetRow(
            student_id=s.id, roll_no=s.roll_no, student_name=s.full_name,
            marks_obtained=marks[s.id].marks_obtained if s.id in marks else None,
            is_absent=marks[s.id].is_absent if s.id in marks else False,
            remarks=marks[s.id].remarks if s.id in marks else None,
        )
        for s in students
    ]
    out = service.schedule_to_out(db.execute(service.schedule_query().where(ExamSchedule.id == schedule.id)).first())
    return MarkSheetOut(schedule=out, exam_status=exam.status, rows=rows)


@router.put("/exam-schedules/{schedule_id}/marks")
def enter_marks(schedule_id: uuid.UUID, payload: MarksBulkIn, db: Session = Depends(get_db), user: User = STAFF):
    schedule = get_or_404(db, ExamSchedule, schedule_id, "Paper")
    service.ensure_can_enter_marks(db, user, schedule)
    saved = service.upsert_marks(db, user, schedule, payload.entries)
    db.commit()
    return {"saved": saved}


# ---------------------------------------------------------------- grade scale
@router.get("/grade-scales", response_model=list[GradeBandOut])
def get_grade_scales(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return results_service.load_scale(db)


@router.put("/grade-scales", response_model=list[GradeBandOut])
def put_grade_scales(payload: GradeScaleIn, db: Session = Depends(get_db), user: User = ADMIN):
    service.replace_scale(db, payload.bands)
    db.commit()
    return results_service.load_scale(db)


# ---------------------------------------------------------------- results
@router.get("/results/students/{student_id}", response_model=StudentResultsOut)
def get_student_results(
    student_id: uuid.UUID,
    exam_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not can_access_student(user, student_id, db):
        raise not_found("Student")  # also hides that the student exists
    published_only = user.role in ("student", "parent")
    return StudentResultsOut(
        student_id=student_id, results=results_service.student_results(db, student_id, exam_id, published_only)
    )


@router.get("/results/sections/{section_id}", response_model=list[StudentExamResult])
def get_section_results(
    section_id: uuid.UUID,
    exam_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    user: User = STAFF,
):
    require_section_visible(user, db, section_id, "Section")
    get_or_404(db, Exam, exam_id, "Exam")
    return results_service.compute_section_results(db, exam_id, section_id)
