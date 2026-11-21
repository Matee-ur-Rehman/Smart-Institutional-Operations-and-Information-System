import uuid
from datetime import date, time
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, Date, ForeignKey, Numeric, String, Time, UniqueConstraint, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UUIDPk, in_check

EXAM_TYPES = ("monthly", "midterm", "final", "other")
EXAM_STATUSES = ("draft", "scheduled", "ongoing", "completed", "results_published")


class GradeScale(UUIDPk, Base):
    __tablename__ = "grade_scales"

    grade: Mapped[str] = mapped_column(String(3), nullable=False, unique=True)
    min_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    max_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    gpa_points: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    remark: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    is_pass: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class Exam(UUIDPk, Timestamps, Base):
    __tablename__ = "exams"
    __table_args__ = (
        CheckConstraint(in_check("exam_type", EXAM_TYPES), name="exam_type"),
        CheckConstraint(in_check("status", EXAM_STATUSES), name="status"),
        CheckConstraint("end_date >= start_date", name="dates"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    exam_type: Mapped[str] = mapped_column(String(20), nullable=False)
    academic_year_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("academic_years.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(25), nullable=False, default="draft", server_default="draft")


class ExamSchedule(UUIDPk, Timestamps, Base):
    __tablename__ = "exam_schedules"
    __table_args__ = (
        UniqueConstraint("exam_id", "section_id", "subject_id"),
        CheckConstraint("total_marks > 0", name="total_positive"),
        CheckConstraint("passing_marks >= 0 AND passing_marks <= total_marks", name="passing_range"),
        CheckConstraint("end_time > start_time", name="times"),
    )

    exam_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exams.id"), nullable=False)
    section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sections.id"), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    exam_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    room: Mapped[str | None] = mapped_column(String(30))
    total_marks: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    passing_marks: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)


class Mark(UUIDPk, Timestamps, Base):
    __tablename__ = "marks"
    __table_args__ = (
        UniqueConstraint("exam_schedule_id", "student_id"),
        CheckConstraint("marks_obtained IS NULL OR marks_obtained >= 0", name="non_negative"),
    )

    exam_schedule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exam_schedules.id"), nullable=False)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id"), nullable=False)
    marks_obtained: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    is_absent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    remarks: Mapped[str | None] = mapped_column(String(200))
    entered_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
