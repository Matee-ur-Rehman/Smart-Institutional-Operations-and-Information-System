import uuid
from datetime import date, time
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Numeric, String, Time, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.ops_common.base import TimestampMixin, check_in, uuid_pk

EXAM_TYPES = ["monthly", "midterm", "final", "other"]
EXAM_STATUSES = ["draft", "scheduled", "ongoing", "completed", "results_published"]


class GradeScale(Base):
    __tablename__ = "grade_scales"

    id: Mapped[uuid.UUID] = uuid_pk()
    grade: Mapped[str] = mapped_column(String(3), unique=True, nullable=False)
    min_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    max_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    gpa_points: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    remark: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    is_pass: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class Exam(TimestampMixin, Base):
    __tablename__ = "exams"
    __table_args__ = (
        check_in("exams", "exam_type", EXAM_TYPES),
        check_in("exams", "status", EXAM_STATUSES),
        CheckConstraint("end_date >= start_date", name="ck_exams_dates"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    exam_type: Mapped[str] = mapped_column(String(20), nullable=False)
    academic_year_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("academic_years.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")


class ExamSchedule(TimestampMixin, Base):
    __tablename__ = "exam_schedules"
    __table_args__ = (
        UniqueConstraint("exam_id", "section_id", "subject_id"),
        CheckConstraint("passing_marks <= total_marks", name="ck_exam_schedules_passing"),
        CheckConstraint("end_time > start_time", name="ck_exam_schedules_times"),
        CheckConstraint("total_marks > 0", name="ck_exam_schedules_total_positive"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    exam_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("exams.id", ondelete="CASCADE"), nullable=False, index=True)
    section_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("sections.id"), nullable=False, index=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("subjects.id"), nullable=False)
    exam_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    room: Mapped[str | None] = mapped_column(String(30))
    total_marks: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    passing_marks: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)


class Mark(TimestampMixin, Base):
    __tablename__ = "marks"
    __table_args__ = (
        UniqueConstraint("exam_schedule_id", "student_id"),
        CheckConstraint("marks_obtained IS NULL OR marks_obtained >= 0", name="ck_marks_non_negative"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    exam_schedule_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("exam_schedules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("students.id"), nullable=False, index=True)
    marks_obtained: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    is_absent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    remarks: Mapped[str | None] = mapped_column(String(200))
    entered_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
