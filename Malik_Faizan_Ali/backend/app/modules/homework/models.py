import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.common.timeutil import school_today
from app.core.database import Base, Timestamps, UUIDPk, in_check

ASSIGNMENT_STATUSES = ("draft", "published", "closed")


class Assignment(UUIDPk, Timestamps, Base):
    __tablename__ = "assignments"
    __table_args__ = (
        CheckConstraint(in_check("status", ASSIGNMENT_STATUSES), name="status"),
        CheckConstraint("due_date >= assigned_date", name="due_after_assigned"),
        Index("ix_assignments_section_due", "section_id", "due_date"),
    )

    teacher_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teachers.id"), nullable=False)
    section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sections.id"), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    assigned_date: Mapped[date] = mapped_column(Date, nullable=False, default=school_today, server_default=text("CURRENT_DATE"))
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    max_marks: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    attachment_path: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="published", server_default="published")


class AssignmentSubmission(UUIDPk, Base):
    """Created now but DISABLED: no student endpoints exist (decision 2026-10-21)."""
    __tablename__ = "assignment_submissions"
    __table_args__ = (UniqueConstraint("assignment_id", "student_id"),)

    assignment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assignments.id"), nullable=False)
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id"), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    file_path: Mapped[str | None] = mapped_column(String(500))
    remarks: Mapped[str | None] = mapped_column(Text)
    marks_obtained: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
