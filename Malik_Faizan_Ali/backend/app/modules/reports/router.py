"""Reports: PDF documents and CSV exports. Authorization mirrors the JSON endpoints of each module."""
import re
import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.scope import require_visible_section, section_labels
from app.core.access import can_access_student, parent_child_ids
from app.core.database import get_db
from app.core.errors import NotFound
from app.core.security import get_current_user, require_roles
from app.modules.attendance.router import _range, _section, _student_report, section_summary
from app.modules.attendance import service as att_service
from app.modules.attendance.models import Attendance
from app.modules.exams import service as exam_service
from app.modules.exams.models import Exam
from app.modules.fees import service as fee_service
from app.modules.fees.models import FeeInvoice, FeePayment
from app.modules.foundation.models import Parent, Section, Student, StudentParent, User
from app.modules.reports import pdf
from app.modules.timetable import service as tt_service

router = APIRouter(prefix="/reports", tags=["Reports"])
staff = Depends(require_roles("admin", "teacher"))
admin_only = Depends(require_roles("admin"))
admin_parent = Depends(require_roles("admin", "parent"))
Format = Literal["pdf", "csv"]


def _slug(*parts: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", "_".join(p for p in parts if p)).strip("_") or "report"


def _file(content: bytes, name: str, fmt: str = "pdf") -> Response:
    media = "application/pdf" if fmt == "pdf" else "text/csv; charset=utf-8"
    return Response(content=content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{name}.{fmt}"'})


# ------------------------------------------------------------------ result card / class results
@router.get("/result-card/{student_id}")
def result_card(student_id: uuid.UUID, exam_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    st = db.get(Student, student_id)
    exam = db.get(Exam, exam_id)
    if st is None or exam is None or not can_access_student(user, student_id, db):
        raise NotFound("Result not found")
    if user.role in ("student", "parent") and exam.status != "results_published":
        raise NotFound("Result not found")                    # unpublished results are never revealed
    data = exam_service.get_result_card_data(db, student_id, exam_id)
    if not data.get("subjects"):
        raise NotFound("This student has no papers in this exam")
    return _file(pdf.result_card(data), _slug("result", st.roll_no, exam.name))


@router.get("/results/sections/{section_id}")
def class_results(section_id: uuid.UUID, exam_id: uuid.UUID, fmt: Format = Query("pdf", alias="format"),
                  user: User = staff, db: Session = Depends(get_db)):
    sec = _section(db, user, section_id)
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise NotFound("Exam not found")
    rows = [exam_service.result_to_dict(r) for r in exam_service.compute_section_results(db, exam, sec.id)]
    rows.sort(key=lambda r: (r.get("position") is None, r.get("position") or 0, r["roll_no"]))
    subjects = sorted({s["subject_name"] for r in rows for s in r["subjects"]})
    label = section_labels(db, [sec.id]).get(sec.id, "")
    name = _slug("results", label, exam.name)
    if fmt == "csv":
        body = [[r.get("position") or "", r["roll_no"], r["full_name"],
                 *[next((s.get("marks_obtained") for s in r["subjects"] if s["subject_name"] == sub), "") for sub in subjects],
                 r.get("total_obtained"), r.get("percentage"), r.get("grade"), r.get("result")] for r in rows]
        return _file(pdf.to_csv(["Position", "Roll No", "Name", *subjects, "Total", "Percentage", "Grade", "Result"], body), name, "csv")
    complete = [r for r in rows if r.get("percentage") is not None]
    summary = {"students": len(rows), "passed": sum(r.get("result") == "pass" for r in rows), "failed": sum(r.get("result") == "fail" for r in rows),
               "average_percentage": round(sum(r["percentage"] for r in complete) / len(complete), 2) if complete else None}
    return _file(pdf.class_results(label, exam.name, rows, subjects, summary), name)


# ------------------------------------------------------------------ fees
@router.get("/fee-receipt/{payment_id}")
def fee_receipt(payment_id: uuid.UUID, user: User = admin_parent, db: Session = Depends(get_db)):
    p = db.get(FeePayment, payment_id)
    inv = db.get(FeeInvoice, p.invoice_id) if p else None
    if inv is None:
        raise NotFound("Payment not found")
    if user.role == "parent" and (inv.student_id not in parent_child_ids(user, db) or inv.status == "cancelled"):
        raise NotFound("Payment not found")
    data = fee_service.get_fee_receipt_data(db, payment_id)
    return _file(pdf.fee_receipt(data), _slug("receipt", data["payment"].receipt_no))


@router.get("/fee-statement/{student_id}")
def fee_statement(student_id: uuid.UUID, user: User = admin_parent, db: Session = Depends(get_db)):
    st = db.get(Student, student_id)
    if st is None or not can_access_student(user, student_id, db):
        raise NotFound("Student not found")
    data = fee_service.get_fee_statement_data(db, student_id)
    if user.role == "parent":                                  # cancelled invoices are an admin matter
        data["invoices"] = [i for i in data["invoices"] if i.status != "cancelled"]
        data["totals"] = fee_service.statement_totals(data["invoices"])
    return _file(pdf.fee_statement(data), _slug("fee_statement", st.roll_no))


# ------------------------------------------------------------------ timetable
@router.get("/timetable/{section_id}")
def timetable(section_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if db.get(Section, section_id) is None:
        raise NotFound("Section not found")
    require_visible_section(user, db, section_id)
    data = tt_service.get_timetable_data(db, section_id)
    return _file(pdf.timetable(data), _slug("timetable", data.get("section_label") or ""))


# ------------------------------------------------------------------ attendance
@router.get("/attendance/students/{student_id}")
def student_attendance(student_id: uuid.UUID, from_date: date | None = None, to_date: date | None = None,
                       fmt: Format = Query("pdf", alias="format"), user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    st = db.get(Student, student_id)
    if st is None or not can_access_student(user, student_id, db):
        raise NotFound("Student not found")
    rep = _student_report(db, st, *_range(from_date, to_date)).model_dump()
    name = _slug("attendance", st.roll_no)
    if fmt == "csv":
        return _file(pdf.to_csv(["Date", "Status", "Remarks"], [[r["date"], r["status"], r["remarks"] or ""] for r in rep["records"]]), name, "csv")
    return _file(pdf.student_attendance(rep), name)


@router.get("/attendance/sections/{section_id}")
def section_attendance(section_id: uuid.UUID, from_date: date | None = None, to_date: date | None = None,
                       fmt: Format = Query("pdf", alias="format"), user: User = staff, db: Session = Depends(get_db)):
    sec = _section(db, user, section_id)
    data = section_summary(sec.id, from_date, to_date, user, db)
    name = _slug("attendance", data["section_label"] or "")
    if fmt == "csv":
        rows = [[r["roll_no"], r["full_name"], r["summary"].present, r["summary"].late, r["summary"].absent, r["summary"].leave,
                 r["summary"].total_days, r["summary"].percentage if r["summary"].percentage is not None else "",
                 "LOW" if r["low_attendance"] else ""] for r in data["students"]]
        return _file(pdf.to_csv(["Roll No", "Name", "Present", "Late", "Absent", "Leave", "Days", "Percentage", "Flag"], rows), name, "csv")
    return _file(pdf.section_attendance(data), name)


# ------------------------------------------------------------------ student list (admin)
@router.get("/students")
def student_list(section_id: uuid.UUID | None = None, user: User = admin_only, db: Session = Depends(get_db)):
    stmt = select(Student).where(Student.is_active).order_by(Student.roll_no)
    if section_id:
        stmt = stmt.where(Student.section_id == section_id)
    students = list(db.scalars(stmt))
    labels = section_labels(db, {s.section_id for s in students})
    parents: dict[uuid.UUID, list[str]] = {}
    for sid, name, phone in db.execute(select(StudentParent.student_id, User.full_name, User.phone)
                                       .join(Parent, Parent.id == StudentParent.parent_id).join(User, User.id == Parent.user_id)):
        parents.setdefault(sid, []).append(f"{name} ({phone})" if phone else name)
    rows = [[s.roll_no, s.full_name, labels.get(s.section_id, ""), s.gender or "", s.date_of_birth or "", s.admission_date or "",
             "; ".join(parents.get(s.id, []))] for s in students]
    return _file(pdf.to_csv(["Roll No", "Name", "Class/Section", "Gender", "Date of Birth", "Admission Date", "Parents"], rows),
                 "students", "csv")
