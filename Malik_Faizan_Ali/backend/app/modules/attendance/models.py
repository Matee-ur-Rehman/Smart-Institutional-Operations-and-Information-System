import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UUIDPk, in_check

ATTENDANCE_STATUSES = ("present", "absent", "late", "leave")


class Attendance(UUIDPk, Timestamps, Base):
    """One row per student per school day. `section_id` is the section at the time of marking."""
    __tablename__ = "attendance"
    __table_args__ = (
        CheckConstraint(in_check("status", ATTENDANCE_STATUSES), name="status"),
        UniqueConstraint("student_id", "attendance_date", name="student_date"),
        Index("ix_attendance_section_date", "section_id", "attendance_date"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sections.id"), nullable=False)
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    remarks: Mapped[str | None] = mapped_column(String(200))
    marked_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
