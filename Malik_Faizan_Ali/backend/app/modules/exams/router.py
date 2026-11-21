import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, delete, func, or_, select, tuple_
from sqlalchemy.orm import Session

from app.common.pagination import Page, PageParams, page_params, paginate
from app.common.scope import (
    child_section_ids, current_year_id, linked_child, own_student, section_labels, teacher_pairs,
    teacher_teaches_section, visible_section_ids,
)
from app.core.access import can_access_student, teacher_id_for, teacher_teaches
from app.core.database import get_db
from app.core.errors import BadRequest, Conflict, Forbidden, NotFound, ValidationFailed, field_error
from app.core.security import get_current_user, require_roles
from app.modules.exams import service
from app.modules.exams.models import Exam, ExamSchedule, GradeScale, Mark
from app.modules.exams.schemas import (
    ExamCreate, ExamOut, ExamUpdate, GradeBand, GradeScaleBody, MarkSheetOut, MarkSheetRow, MarksBulk,
    ScheduleCreate, ScheduleOut, ScheduleUpdate,
)
from app.modules.foundation.models import AcademicYear, Section, Student, Subject, Teacher, User
from app.modules.notifications.service import notify_section

router = APIRouter(tags=["Exams, Marks & Results"])
admin_only = Depends(require_roles("admin"))
staff = Depends(require_roles("admin", "teacher"))


# ============================================================ exams
def _exam_out(db: Session, exams: list[Exam]) -> list[ExamOut]:
    counts = dict(db.execute(select(ExamSchedule.exam_id, func.count()).where(
        ExamSchedule.exam_id.in_([e.id for e in exams])).group_by(ExamSchedule.exam_id)).all()) if exams else {}
    return [ExamOut(id=e.id, name=e.name, exam_type=e.exam_type, academic_year_id=e.academic_year_id,
                    start_date=e.start_date, end_date=e.end_date, status=e.status,
                    schedule_count=counts.get(e.id, 0)) for e in exams]


def _get_exam(db: Session, user: User, exam_id: uuid.UUID) -> Exam:
    exam = db.get(Exam, exam_id)
    if exam is None or (user.role != "admin" and exam.status == "draft"):
        raise NotFound("Exam not found")
    return exam


@router.post("/exams", response_model=ExamOut, status_code=201)
def create_exam(body: ExamCreate, user: User = admin_only, db: Session = Depends(get_db)):
    year_id = body.academic_year_id or current_year_id(db)
    if db.get(AcademicYear, year_id) is None:
        raise ValidationFailed(errors=[field_error("academic_year_id", "Academic year does not exist")])
    exam = Exam(name=body.name.strip(), exam_type=body.exam_type, academic_year_id=year_id,
                start_date=body.start_date, end_date=body.end_date, status=body.status)
    db.add(exam)
    db.commit()
    return _exam_out(db, [exam])[0]


@router.get("/exams", response_model=Page[ExamOut])
def list_exams(status: Literal["draft", "scheduled", "ongoing", "completed", "results_published"] | None = None,
               exam_type: Literal["monthly", "midterm", "final", "other"] | None = None,
               academic_year_id: uuid.UUID | None = None, params: PageParams = Depends(page_params),
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(Exam)
    if user.role != "admin":
        stmt = stmt.where(Exam.status != "draft")
    if status:
        stmt = stmt.where(Exam.status == status)
    if exam_type:
        stmt = stmt.where(Exam.exam_type == exam_type)
    if academic_year_id:
        stmt = stmt.where(Exam.academic_year_id == academic_year_id)
    rows, total = paginate(db, stmt.order_by(Exam.start_date.desc(), Exam.id), params)
    return Page(items=_exam_out(db, [r[0] for r in rows]), total=total, page=params.page, page_size=params.page_size)


@router.get("/exams/{exam_id}", response_model=ExamOut)
def get_exam(exam_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _exam_out(db, [_get_exam(db, user, exam_id)])[0]


@router.patch("/exams/{exam_id}", response_model=ExamOut)
def update_exam(exam_id: uuid.UUID, body: ExamUpdate, user: User = admin_only, db: Session = Depends(get_db)):
    exam = _get_exam(db, user, exam_id)
    data = body.model_dump(exclude_unset=True)
    if exam.status == "results_published" and data.get("status"):
        raise Conflict("Results are already published; the status can no longer be changed")
    for k, v in data.items():
        if v is not None:
            setattr(exam, k, v.strip() if k == "name" else v)
    if exam.end_date < exam.start_date:
        raise ValidationFailed(errors=[field_error("end_date", "end_date cannot be before start_date")])
    db.commit()
    return _exam_out(db, [exam])[0]


@router.delete("/exams/{exam_id}", status_code=204)
def delete_exam(exam_id: uuid.UUID, user: User = admin_only, db: Session = Depends(get_db)):
    exam = _get_exam(db, user, exam_id)
    if exam.status != "draft":
        raise BadRequest("Only draft exams can be deleted", code="exam_not_draft")
    ids = list(db.scalars(select(ExamSchedule.id).where(ExamSchedule.exam_id == exam.id)))
    if ids and db.scalar(select(func.count()).select_from(Mark).where(Mark.exam_schedule_id.in_(ids))):
        raise Conflict("This exam already has marks entered and cannot be deleted")
    db.execute(delete(ExamSchedule).where(ExamSchedule.exam_id == exam.id))
    db.delete(exam)
    db.commit()


# ============================================================ schedules
def _times_overlap(a_start, a_end, b_start, b_end) -> bool:
    return a_start < b_end and b_start < a_end


def _validate_schedule(db: Session, exam: Exam, section_id, subject_id, d: date, start, end, exclude_id=None):
    errors = []
    if not (exam.start_date <= d <= exam.end_date):
        errors.append(field_error("exam_date", f"Date must be within the exam window ({exam.start_date} to {exam.end_date})"))
    if errors:
        raise ValidationFailed(errors=errors)
    same_day = db.scalars(select(ExamSchedule).where(
        ExamSchedule.exam_id == exam.id, ExamSchedule.section_id == section_id, ExamSchedule.exam_date == d))
    for other in same_day:
        if other.id != exclude_id and _times_overlap(start, end, other.start_time, other.end_time):
            raise Conflict("This section already has another paper at that time", code="schedule_clash")


@router.post("/exams/{exam_id}/schedules", response_model=ScheduleOut, status_code=201)
def create_schedule(exam_id: uuid.UUID, body: ScheduleCreate, user: User = admin_only, db: Session = Depends(get_db)):
    exam = _get_exam(db, user, exam_id)
    if exam.status == "results_published":
        raise Conflict("Results are published; the schedule can no longer change")
    errors = []
    if db.get(Section, body.section_id) is None:
        errors.append(field_error("section_id", "Section does not exist"))
    if db.get(Subject, body.subject_id) is None:
        errors.append(field_error("subject_id", "Subject does not exist"))
    if errors:
        raise ValidationFailed(errors=errors)
    if db.scalar(select(ExamSchedule.id).where(ExamSchedule.exam_id == exam.id, ExamSchedule.section_id == body.section_id,
                                               ExamSchedule.subject_id == body.subject_id)):
        raise Conflict("A paper for this section and subject already exists in this exam", code="duplicate_schedule")
    _validate_schedule(db, exam, body.section_id, body.subject_id, body.exam_date, body.start_time, body.end_time)
    s = ExamSchedule(exam_id=exam.id, **body.model_dump())
    db.add(s)
    db.commit()
    return service.schedule_out(db, [s], True)[0]


def _scoped_schedules(user: User, db: Session):
    stmt = select(ExamSchedule).join(Exam, Exam.id == ExamSchedule.exam_id)
    if user.role == "admin":
        return stmt
    stmt = stmt.where(Exam.status != "draft")
    if user.role == "teacher":
        tid = db.scalar(select(Teacher.id).where(Teacher.user_id == user.id, Teacher.is_active))
        pairs = teacher_pairs(db, tid) if tid else set()
        return stmt.where(tuple_(ExamSchedule.section_id, ExamSchedule.subject_id).in_(list(pairs))) if pairs else stmt.where(False)
    secs = visible_section_ids(user, db) or set()
    return stmt.where(ExamSchedule.section_id.in_(list(secs))) if secs else stmt.where(False)


@router.get("/exams/{exam_id}/schedules", response_model=list[ScheduleOut])
def list_schedules(exam_id: uuid.UUID, section_id: uuid.UUID | None = None, subject_id: uuid.UUID | None = None,
                   student_id: uuid.UUID | None = None, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    _get_exam(db, user, exam_id)
    stmt = _scoped_schedules(user, db).where(ExamSchedule.exam_id == exam_id)
    if student_id:
        if user.role == "parent":
            linked_child(user, db, student_id)
        elif not can_access_student(user, student_id, db):
            raise NotFound("Student not found")
        stmt = stmt.where(ExamSchedule.section_id == db.scalar(select(Student.section_id).where(Student.id == student_id)))
    if section_id:
        stmt = stmt.where(ExamSchedule.section_id == section_id)
    if subject_id:
        stmt = stmt.where(ExamSchedule.subject_id == subject_id)
    rows = list(db.scalars(stmt.order_by(ExamSchedule.exam_date, ExamSchedule.start_time, ExamSchedule.section_id)))
    return service.schedule_out(db, rows, user.role in ("admin", "teacher"))


def _schedule_or_404(db: Session, schedule_id: uuid.UUID) -> ExamSchedule:
    s = db.get(ExamSchedule, schedule_id)
    if s is None:
        raise NotFound("Exam schedule not found")
    return s


@router.patch("/exam-schedules/{schedule_id}", response_model=ScheduleOut)
def update_schedule(schedule_id: uuid.UUID, body: ScheduleUpdate, user: User = admin_only, db: Session = Depends(get_db)):
    s = _schedule_or_404(db, schedule_id)
    exam = db.get(Exam, s.exam_id)
    if exam.status == "results_published":
        raise Conflict("Results are published; the schedule can no longer change")
    data = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None or k == "room"}
    new = {**{c: getattr(s, c) for c in ("exam_date", "start_time", "end_time", "total_marks", "passing_marks")}, **data}
    if new["end_time"] <= new["start_time"]:
        raise ValidationFailed(errors=[field_error("end_time", "end_time must be after start_time")])
    if new["passing_marks"] > new["total_marks"]:
        raise ValidationFailed(errors=[field_error("passing_marks", "passing_marks cannot exceed total_marks")])
    if "total_marks" in data and db.scalar(select(func.count()).select_from(Mark).where(
            Mark.exam_schedule_id == s.id, Mark.marks_obtained > new["total_marks"])):
        raise Conflict("Existing marks are higher than the new total marks", code="marks_exceed_total")
    _validate_schedule(db, exam, s.section_id, s.subject_id, new["exam_date"], new["start_time"], new["end_time"], s.id)
    for k, v in data.items():
        setattr(s, k, v)
    db.commit()
    return service.schedule_out(db, [s], True)[0]


@router.delete("/exam-schedules/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: uuid.UUID, user: User = admin_only, db: Session = Depends(get_db)):
    s = _schedule_or_404(db, schedule_id)
    if db.get(Exam, s.exam_id).status == "results_published":
        raise Conflict("Results are published; the schedule can no longer change")
    if db.scalar(select(func.count()).select_from(Mark).where(Mark.exam_schedule_id == s.id)):
        raise Conflict("Marks have been entered for this paper and it cannot be deleted")
    db.delete(s)
    db.commit()


# ============================================================ marks
def _marks_schedule(db: Session, user: User, schedule_id: uuid.UUID) -> tuple[ExamSchedule, Exam]:
    s = _schedule_or_404(db, schedule_id)
    if user.role == "teacher" and not teacher_teaches(db, teacher_id_for(user, db), s.section_id, s.subject_id):
        raise Forbidden("You do not teach this subject in this section")
    return s, db.get(Exam, s.exam_id)


def _sheet(db: Session, s: ExamSchedule, exam: Exam) -> MarkSheetOut:
    bands = service.load_bands(db)
    marks = {m.student_id: m for m in db.scalars(select(Mark).where(Mark.exam_schedule_id == s.id))}
    rows = []
    for sid, roll, name in db.execute(select(Student.id, Student.roll_no, Student.full_name).where(
            Student.section_id == s.section_id, Student.is_active).order_by(Student.roll_no)).all():
        m = marks.get(sid)
        pct = grade = passed = None
        if m is not None and (m.marks_obtained is not None or m.is_absent):
            obtained = Decimal(0) if m.is_absent else Decimal(m.marks_obtained)
            pct = service.q2(obtained / s.total_marks * 100)
            b = service.band_for(bands, pct)
            grade = b.grade if b else None
            passed = (not m.is_absent) and obtained >= s.passing_marks
        rows.append(MarkSheetRow(student_id=sid, roll_no=roll, full_name=name,
                                 marks_obtained=m.marks_obtained if m else None, is_absent=bool(m and m.is_absent),
                                 remarks=m.remarks if m else None, percentage=pct, grade=grade, passed=passed))
    return MarkSheetOut(schedule=service.schedule_out(db, [s], True)[0], exam_status=exam.status,
                        locked=exam.status in ("draft", "results_published"), rows=rows)


@router.get("/exam-schedules/{schedule_id}/marks", response_model=MarkSheetOut)
def get_mark_sheet(schedule_id: uuid.UUID, user: User = staff, db: Session = Depends(get_db)):
    s, exam = _marks_schedule(db, user, schedule_id)
    return _sheet(db, s, exam)


@router.put("/exam-schedules/{schedule_id}/marks", response_model=MarkSheetOut)
def save_marks(schedule_id: uuid.UUID, body: MarksBulk, user: User = staff, db: Session = Depends(get_db)):
    s, exam = _marks_schedule(db, user, schedule_id)
    if exam.status == "results_published":
        raise Conflict("Results are published; marks can no longer be changed", code="results_published")
    if exam.status == "draft":
        raise BadRequest("Marks cannot be entered until the exam is scheduled", code="exam_not_open")

    in_section = set(db.scalars(select(Student.id).where(Student.section_id == s.section_id, Student.is_active)))
    existing = {m.student_id: m for m in db.scalars(select(Mark).where(Mark.exam_schedule_id == s.id))}
    errors, seen = [], set()
    for i, e in enumerate(body.entries):
        f = f"entries.{i}"
        if e.student_id in seen:
            errors.append(field_error(f"{f}.student_id", "Student appears more than once"))
        seen.add(e.student_id)
        if e.student_id not in in_section:
            errors.append(field_error(f"{f}.student_id", "Student is not in this section"))
        if e.is_absent and e.marks_obtained is not None:
            errors.append(field_error(f"{f}.marks_obtained", "An absent student cannot have marks"))
        if e.marks_obtained is not None and e.marks_obtained < 0:
            errors.append(field_error(f"{f}.marks_obtained", "Marks cannot be negative"))
        if e.marks_obtained is not None and e.marks_obtained > s.total_marks:
            errors.append(field_error(f"{f}.marks_obtained", f"Marks cannot exceed {s.total_marks}"))
    if errors:
        raise ValidationFailed(errors=errors)

    for e in body.entries:
        m = existing.get(e.student_id)
        empty = e.marks_obtained is None and not e.is_absent and not e.remarks
        if empty:
            if m is not None:
                db.delete(m)
            continue
        if m is None:
            m = Mark(exam_schedule_id=s.id, student_id=e.student_id, entered_by=user.id)
            db.add(m)
        m.marks_obtained, m.is_absent, m.remarks, m.entered_by = e.marks_obtained, e.is_absent, e.remarks, user.id
    db.commit()
    return _sheet(db, s, exam)


@router.post("/exams/{exam_id}/publish-results", response_model=dict)
def publish_results(exam_id: uuid.UUID, user: User = admin_only, db: Session = Depends(get_db)):
    exam = _get_exam(db, user, exam_id)
    if exam.status == "results_published":
        raise Conflict("Results are already published")
    if exam.status == "draft":
        raise BadRequest("Schedule the exam before publishing results", code="exam_not_open")
    section_ids = service.sections_of_exam(db, exam.id)
    if not section_ids:
        raise BadRequest("This exam has no papers scheduled", code="no_schedules")
    sched_ids = list(db.scalars(select(ExamSchedule.id).where(ExamSchedule.exam_id == exam.id)))
    entered = db.scalar(select(func.count()).select_from(Mark).where(Mark.exam_schedule_id.in_(sched_ids))) or 0
    if entered == 0:
        raise BadRequest("No marks have been entered yet", code="no_marks")
    exam.status = "results_published"
    notified = 0
    for sid in section_ids:
        notified += notify_section(db, sid, f"Results published: {exam.name}",
                                   f"The results of {exam.name} are now available.", "marks",
                                   reference_type="exam", reference_id=exam.id)
    db.commit()
    return {"exam_id": exam.id, "status": exam.status, "notified": notified}


# ============================================================ grade scale
def _bands_out(db: Session) -> dict:
    return {"bands": [GradeBand.model_validate(b) for b in service.load_bands(db)]}


@router.get("/grade-scales", response_model=GradeScaleBody)
def get_grade_scale(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _bands_out(db)


@router.put("/grade-scales", response_model=GradeScaleBody)
def put_grade_scale(body: GradeScaleBody, user: User = admin_only, db: Session = Depends(get_db)):
    bands = sorted(body.bands, key=lambda b: b.min_percentage)
    errors = []
    if bands[0].min_percentage != 0:
        errors.append(field_error("bands", "The lowest band must start at 0%"))
    if bands[-1].max_percentage != 100:
        errors.append(field_error("bands", "The highest band must end at 100%"))
    if len({b.grade for b in bands}) != len(bands):
        errors.append(field_error("bands", "Grade names must be unique"))
    for a, b in zip(bands, bands[1:]):
        if b.min_percentage <= a.max_percentage:
            errors.append(field_error("bands", f"Bands {a.grade} and {b.grade} overlap"))
        elif b.min_percentage - a.max_percentage > Decimal("1.00"):
            errors.append(field_error("bands", f"There is a gap between {a.grade} and {b.grade}"))
    if errors:
        raise ValidationFailed(errors=errors)
    db.execute(delete(GradeScale))
    db.add_all(GradeScale(**b.model_dump()) for b in bands)
    db.commit()
    return _bands_out(db)


# ============================================================ results
def _result_student(db: Session, user: User, student_id: uuid.UUID) -> Student:
    st = db.get(Student, student_id)
    if st is None or not can_access_student(user, student_id, db):
        raise NotFound("Student not found")
    return st


@router.get("/results/students/{student_id}")
def student_results(student_id: uuid.UUID, exam_id: uuid.UUID | None = None, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    st = _result_student(db, user, student_id)
    published_only = user.role in ("student", "parent")
    stmt = select(Exam).join(ExamSchedule, ExamSchedule.exam_id == Exam.id).where(
        ExamSchedule.section_id == st.section_id, Exam.status != "draft").distinct()
    if published_only:
        stmt = stmt.where(Exam.status == "results_published")
    if exam_id:
        stmt = stmt.where(Exam.id == exam_id)
    exams = list(db.scalars(stmt.order_by(Exam.start_date.desc())))
    if exam_id and not exams:
        raise NotFound("Result not found")
    bands = service.load_bands(db)
    sec = section_labels(db, [st.section_id]).get(st.section_id)
    return {"student": {"id": st.id, "roll_no": st.roll_no, "full_name": st.full_name, "section_id": st.section_id,
                        "section_label": sec},
            "results": [service.student_exam_result(db, st, e, bands) for e in exams]}


@router.get("/results/sections/{section_id}")
def section_results(section_id: uuid.UUID, exam_id: uuid.UUID = Query(...), user: User = staff,
                    db: Session = Depends(get_db)):
    if db.get(Section, section_id) is None:
        raise NotFound("Section not found")
    if user.role == "teacher" and not teacher_teaches_section(db, teacher_id_for(user, db), section_id):
        raise NotFound("Section not found")
    exam = _get_exam(db, user, exam_id)
    rows = service.compute_section_results(db, exam, section_id)
    complete = [r for r in rows if r.percentage is not None]
    subj: dict[str, list[Decimal]] = {}
    for r in rows:
        for s in r.subjects:
            if s.percentage is not None:
                subj.setdefault(s.subject_name, []).append(s.percentage)
    rows_sorted = sorted(rows, key=lambda r: (r.position is None, r.position or 0, r.roll_no))
    return {
        "section_id": section_id, "section_label": section_labels(db, [section_id]).get(section_id),
        "exam": service.exam_to_dict(db, exam),
        "summary": {
            "students": len(rows), "passed": sum(r.result == "pass" for r in rows),
            "failed": sum(r.result == "fail" for r in rows), "incomplete": sum(r.result == "incomplete" for r in rows),
            "average_percentage": service.q2(sum(r.percentage for r in complete) / len(complete)) if complete else None,
            "highest_percentage": max((r.percentage for r in complete), default=None),
            "lowest_percentage": min((r.percentage for r in complete), default=None),
            "subject_averages": [{"subject_name": k, "average_percentage": service.q2(sum(v) / len(v))}
                                 for k, v in sorted(subj.items())],
        },
        "students": [service.result_to_dict(r) for r in rows_sorted],
    }
