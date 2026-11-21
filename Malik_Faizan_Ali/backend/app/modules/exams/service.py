"""Exam business logic: grade lookup, result computation, mark sheets, notifications."""
import uuid
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.scope import section_labels, subject_names
from app.core.errors import NotFound
from app.modules.exams.models import Exam, ExamSchedule, GradeScale, Mark
from app.modules.exams.schemas import ScheduleOut
from app.modules.foundation.models import Section, Student

TWO = Decimal("0.01")


def q2(v: Decimal | float | int | None) -> Decimal | None:
    return None if v is None else Decimal(v).quantize(TWO, rounding=ROUND_HALF_UP)


# ------------------------------------------------------------------ grades
def load_bands(db: Session) -> list[GradeScale]:
    return list(db.scalars(select(GradeScale).order_by(GradeScale.min_percentage.desc())))


def band_for(bands: list[GradeScale], pct: Decimal | None) -> GradeScale | None:
    if pct is None:
        return None
    for b in bands:  # sorted by min desc: first band whose minimum is reached
        if pct >= b.min_percentage:
            return b
    return bands[-1] if bands else None


# ------------------------------------------------------------------ results
@dataclass
class SubjectResult:
    schedule_id: uuid.UUID
    subject_id: uuid.UUID
    subject_name: str
    exam_date: object
    total_marks: Decimal
    passing_marks: Decimal
    state: str                      # entered | absent | pending
    marks_obtained: Decimal | None
    percentage: Decimal | None
    grade: str | None
    passed: bool | None
    remarks: str | None


@dataclass
class StudentResult:
    student_id: uuid.UUID
    roll_no: str
    full_name: str
    subjects: list[SubjectResult] = field(default_factory=list)
    total_obtained: Decimal = Decimal(0)
    total_marks: Decimal = Decimal(0)
    percentage: Decimal | None = None
    grade: str | None = None
    result: str = "incomplete"      # pass | fail | incomplete
    is_complete: bool = False
    position: int | None = None


def compute_section_results(db: Session, exam: Exam, section_id: uuid.UUID, bands=None) -> list[StudentResult]:
    bands = bands if bands is not None else load_bands(db)
    schedules = list(db.scalars(select(ExamSchedule).where(
        ExamSchedule.exam_id == exam.id, ExamSchedule.section_id == section_id)
        .order_by(ExamSchedule.exam_date, ExamSchedule.start_time)))
    students = list(db.execute(select(Student.id, Student.roll_no, Student.full_name).where(
        Student.section_id == section_id, Student.is_active).order_by(Student.roll_no)).all())
    names = subject_names(db, {s.subject_id for s in schedules})
    marks = {}
    if schedules:
        for m in db.scalars(select(Mark).where(Mark.exam_schedule_id.in_([s.id for s in schedules]))):
            marks[(m.exam_schedule_id, m.student_id)] = m

    results: list[StudentResult] = []
    for sid, roll, name in students:
        r = StudentResult(student_id=sid, roll_no=roll, full_name=name)
        any_fail = any_pending = False
        for s in schedules:
            m = marks.get((s.id, sid))
            if m is not None and m.is_absent:
                state, obtained = "absent", Decimal(0)
            elif m is not None and m.marks_obtained is not None:
                state, obtained = "entered", Decimal(m.marks_obtained)
            else:
                state, obtained = "pending", None
            pct = passed = grade = None
            if obtained is not None:
                pct = q2(obtained / s.total_marks * 100)
                b = band_for(bands, pct)
                grade = b.grade if b else None
                passed = state != "absent" and obtained >= s.passing_marks
                r.total_obtained += obtained
                r.total_marks += s.total_marks
                any_fail = any_fail or not passed
            else:
                any_pending = True
            r.subjects.append(SubjectResult(s.id, s.subject_id, names.get(s.subject_id, "?"), s.exam_date, s.total_marks,
                                            s.passing_marks, state, q2(obtained), pct, grade, passed,
                                            m.remarks if m else None))
        if r.total_marks > 0:
            r.percentage = q2(r.total_obtained / r.total_marks * 100)
            b = band_for(bands, r.percentage)
            r.grade = b.grade if b else None
        r.total_obtained = q2(r.total_obtained)
        r.total_marks = q2(r.total_marks)
        r.is_complete = bool(schedules) and not any_pending
        r.result = "fail" if any_fail else ("pass" if r.is_complete else "incomplete")
        results.append(r)

    complete = sorted((r for r in results if r.is_complete), key=lambda r: r.percentage, reverse=True)
    pos, prev = 0, None
    for i, r in enumerate(complete, start=1):
        if r.percentage != prev:
            pos, prev = i, r.percentage
        r.position = pos
    return results


def result_to_dict(r: StudentResult) -> dict:
    return {
        "student_id": r.student_id, "roll_no": r.roll_no, "full_name": r.full_name,
        "subjects": [{
            "schedule_id": s.schedule_id, "subject_id": s.subject_id, "subject_name": s.subject_name,
            "exam_date": s.exam_date, "total_marks": s.total_marks, "passing_marks": s.passing_marks,
            "state": s.state, "marks_obtained": s.marks_obtained, "percentage": s.percentage, "grade": s.grade,
            "passed": s.passed, "remarks": s.remarks} for s in r.subjects],
        "total_obtained": r.total_obtained, "total_marks": r.total_marks, "percentage": r.percentage,
        "grade": r.grade, "result": r.result, "is_complete": r.is_complete, "position": r.position,
    }


def exam_to_dict(db: Session, exam: Exam) -> dict:
    return {"id": exam.id, "name": exam.name, "exam_type": exam.exam_type, "status": exam.status,
            "start_date": exam.start_date, "end_date": exam.end_date}


def student_exam_result(db: Session, student: Student, exam: Exam, bands=None) -> dict:
    rows = compute_section_results(db, exam, student.section_id, bands)
    mine = next((r for r in rows if r.student_id == student.id), None)
    d = result_to_dict(mine) if mine else {}
    d["exam"] = exam_to_dict(db, exam)
    d["section_size"] = len(rows)
    return d


def get_result_card_data(db: Session, student_id: uuid.UUID, exam_id: uuid.UUID) -> dict:
    """Plain-dict data for Member 1's PDF engine (API_CONTRACT.md section 5)."""
    student = db.get(Student, student_id)
    exam = db.get(Exam, exam_id)
    if student is None or exam is None:
        raise NotFound("Student or exam not found")
    sec = section_labels(db, [student.section_id]).get(student.section_id)
    return {"student": {"id": student.id, "roll_no": student.roll_no, "full_name": student.full_name,
                        "section_label": sec},
            **student_exam_result(db, student, exam)}


# ------------------------------------------------------------------ schedules
def schedule_out(db: Session, rows: list[ExamSchedule], with_counts: bool) -> list[ScheduleOut]:
    if not rows:
        return []
    sec = section_labels(db, {r.section_id for r in rows})
    sub = subject_names(db, {r.subject_id for r in rows})
    exams = {e.id: e.name for e in db.scalars(select(Exam).where(Exam.id.in_({r.exam_id for r in rows})))}
    entered, counts = {}, {}
    if with_counts:
        entered = dict(db.execute(select(Mark.exam_schedule_id, func.count()).where(
            Mark.exam_schedule_id.in_([r.id for r in rows]),
            (Mark.marks_obtained.is_not(None)) | (Mark.is_absent.is_(True))).group_by(Mark.exam_schedule_id)).all())
        counts = dict(db.execute(select(Student.section_id, func.count()).where(
            Student.section_id.in_({r.section_id for r in rows}), Student.is_active).group_by(Student.section_id)).all())
    return [ScheduleOut(
        id=r.id, exam_id=r.exam_id, exam_name=exams.get(r.exam_id, ""), section_id=r.section_id,
        section_label=sec.get(r.section_id), subject_id=r.subject_id, subject_name=sub.get(r.subject_id),
        exam_date=r.exam_date, start_time=r.start_time, end_time=r.end_time, room=r.room,
        total_marks=r.total_marks, passing_marks=r.passing_marks,
        marks_entered=entered.get(r.id, 0) if with_counts else None,
        student_count=counts.get(r.section_id, 0) if with_counts else None) for r in rows]


def sections_of_exam(db: Session, exam_id: uuid.UUID) -> list[uuid.UUID]:
    return list(db.scalars(select(ExamSchedule.section_id).where(ExamSchedule.exam_id == exam_id).distinct()))
