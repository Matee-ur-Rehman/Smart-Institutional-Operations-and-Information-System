"""Result calculation. Results are COMPUTED from marks + exam schedules + grade scale, never stored
(docs/DATABASE_SCHEMA.md section 3). Everything here is plain functions so Member 1's PDF code can
call get_result_card_data() directly."""
import uuid
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.exams.models import Exam, ExamSchedule, GradeScale, Mark
from app.modules.ops_common.base import Money
from app.modules.ops_common.core_refs import SchoolClass, Section, Student, Subject
from app.modules.ops_common.scope import not_found

TWO_PLACES = Decimal("0.01")


class SubjectResult(BaseModel):
    schedule_id: uuid.UUID
    subject_id: uuid.UUID
    subject_name: str
    total_marks: Money
    passing_marks: Money
    status: str  # entered | absent | pending
    marks_obtained: Money | None
    percentage: Money | None
    grade: str | None
    passed: bool | None


class StudentExamResult(BaseModel):
    student_id: uuid.UUID
    roll_no: str
    student_name: str
    subjects: list[SubjectResult]
    total_obtained: Money
    total_marks: Money
    percentage: Money | None
    grade: str | None
    remark: str | None
    complete: bool  # False while any subject still has no marks entered
    passed: bool | None  # None until complete
    position: int | None


class ExamInfo(BaseModel):
    id: uuid.UUID
    name: str
    exam_type: str
    status: str


class ExamResultEntry(BaseModel):
    exam: ExamInfo
    result: StudentExamResult


class StudentResultsOut(BaseModel):
    student_id: uuid.UUID
    results: list[ExamResultEntry]


def percentage_of(obtained: Decimal, total: Decimal) -> Decimal:
    if total == 0:
        return Decimal("0.00")
    return (Decimal(obtained) * 100 / Decimal(total)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def load_scale(db: Session) -> list[GradeScale]:
    return list(db.scalars(select(GradeScale).order_by(GradeScale.min_percentage.desc())))


def grade_for(scale: list[GradeScale], percentage: Decimal) -> GradeScale | None:
    for band in scale:
        if band.min_percentage <= percentage <= band.max_percentage:
            return band
    for band in scale:  # percentage fell in a gap between bands: use the highest band it reaches
        if band.min_percentage <= percentage:
            return band
    return None


def compute_section_results(db: Session, exam_id: uuid.UUID, section_id: uuid.UUID) -> list[StudentExamResult]:
    schedules = db.execute(
        select(ExamSchedule, Subject.name)
        .join(Subject, Subject.id == ExamSchedule.subject_id)
        .where(ExamSchedule.exam_id == exam_id, ExamSchedule.section_id == section_id)
        .order_by(Subject.name)
    ).all()
    students = list(
        db.scalars(
            select(Student).where(Student.section_id == section_id, Student.is_active.is_(True)).order_by(Student.roll_no)
        )
    )
    marks: dict[tuple[uuid.UUID, uuid.UUID], Mark] = {}
    if schedules:
        schedule_ids = [s.id for s, _ in schedules]
        for mark in db.scalars(select(Mark).where(Mark.exam_schedule_id.in_(schedule_ids))):
            marks[(mark.exam_schedule_id, mark.student_id)] = mark
    scale = load_scale(db)

    results: list[StudentExamResult] = []
    entered_counts: dict[uuid.UUID, int] = {}
    for student in students:
        subjects: list[SubjectResult] = []
        total_obtained = Decimal("0")
        total_max = Decimal("0")
        complete = True
        all_passed = True
        entered = 0
        for schedule, subject_name in schedules:
            mark = marks.get((schedule.id, student.id))
            if mark is None:
                complete = False
                subjects.append(
                    SubjectResult(
                        schedule_id=schedule.id, subject_id=schedule.subject_id, subject_name=subject_name,
                        total_marks=schedule.total_marks, passing_marks=schedule.passing_marks, status="pending",
                        marks_obtained=None, percentage=None, grade=None, passed=None,
                    )
                )
                continue
            entered += 1
            obtained = Decimal("0") if mark.is_absent else Decimal(mark.marks_obtained or 0)
            passed = (not mark.is_absent) and obtained >= schedule.passing_marks
            all_passed = all_passed and passed
            total_obtained += obtained
            total_max += schedule.total_marks
            subject_pct = percentage_of(obtained, schedule.total_marks)
            band = grade_for(scale, subject_pct)
            subjects.append(
                SubjectResult(
                    schedule_id=schedule.id, subject_id=schedule.subject_id, subject_name=subject_name,
                    total_marks=schedule.total_marks, passing_marks=schedule.passing_marks,
                    status="absent" if mark.is_absent else "entered",
                    marks_obtained=None if mark.is_absent else obtained,
                    percentage=subject_pct, grade="ABS" if mark.is_absent else (band.grade if band else None),
                    passed=passed,
                )
            )
        overall_pct = percentage_of(total_obtained, total_max) if entered else None
        band = grade_for(scale, overall_pct) if overall_pct is not None else None
        entered_counts[student.id] = entered
        results.append(
            StudentExamResult(
                student_id=student.id, roll_no=student.roll_no, student_name=student.full_name, subjects=subjects,
                total_obtained=total_obtained, total_marks=total_max, percentage=overall_pct,
                grade=band.grade if band else None, remark=band.remark if band else None,
                complete=complete and bool(schedules),
                passed=(all_passed and (band is None or band.is_pass)) if (complete and schedules) else None,
                position=None,
            )
        )

    ranked = sorted((r for r in results if entered_counts[r.student_id] > 0), key=lambda r: r.total_obtained, reverse=True)
    position = 0
    previous_total = None
    for index, item in enumerate(ranked, start=1):
        if item.total_obtained != previous_total:
            position = index
            previous_total = item.total_obtained
        item.position = position
    return results


def _exam_info(exam: Exam) -> ExamInfo:
    return ExamInfo(id=exam.id, name=exam.name, exam_type=exam.exam_type, status=exam.status)


def student_exam_result(db: Session, student_id: uuid.UUID, exam_id: uuid.UUID) -> tuple[Exam, StudentExamResult]:
    exam = db.get(Exam, exam_id)
    student = db.get(Student, student_id)
    if exam is None or student is None:
        raise not_found("Exam or student")
    for item in compute_section_results(db, exam_id, student.section_id):
        if item.student_id == student_id:
            return exam, item
    raise not_found("Result")


def exams_for_student(db: Session, student_id: uuid.UUID, published_only: bool) -> list[Exam]:
    section_id = db.scalar(select(Student.section_id).where(Student.id == student_id))
    if section_id is None:
        return []
    stmt = (
        select(Exam)
        .join(ExamSchedule, ExamSchedule.exam_id == Exam.id)
        .where(ExamSchedule.section_id == section_id)
        .distinct()
        .order_by(Exam.start_date.desc())
    )
    if published_only:
        stmt = stmt.where(Exam.status == "results_published")
    return list(db.scalars(stmt))


def student_results(
    db: Session, student_id: uuid.UUID, exam_id: uuid.UUID | None, published_only: bool
) -> list[ExamResultEntry]:
    if exam_id is not None:
        exam = db.get(Exam, exam_id)
        if exam is None or (published_only and exam.status != "results_published"):
            raise not_found("Result")
        exams = [exam]
    else:
        exams = exams_for_student(db, student_id, published_only)
    out = []
    for exam in exams:
        _, result = student_exam_result(db, student_id, exam.id)
        out.append(ExamResultEntry(exam=_exam_info(exam), result=result))
    return out


# ---- PDF data function for Member 1 (docs/API_CONTRACT.md section 5) ---------------------------
def get_result_card_data(db: Session, student_id: uuid.UUID, exam_id: uuid.UUID) -> dict:
    """Everything a result-card PDF needs. Authorization is the CALLER's job (can_access_student, and
    only published results for students/parents)."""
    exam, result = student_exam_result(db, student_id, exam_id)
    student = db.get(Student, student_id)
    section = db.get(Section, student.section_id)
    school_class = db.get(SchoolClass, section.class_id)
    if exam.status != "results_published":
        raise AppError(409, "conflict", "Results for this exam are not published yet")
    return {
        "exam": _exam_info(exam).model_dump(),
        "student": {
            "id": student.id, "roll_no": student.roll_no, "name": student.full_name,
            "class_name": school_class.name, "section_name": section.name,
        },
        "result": result.model_dump(),
        "section_size": len(compute_section_results(db, exam_id, student.section_id)),
    }
