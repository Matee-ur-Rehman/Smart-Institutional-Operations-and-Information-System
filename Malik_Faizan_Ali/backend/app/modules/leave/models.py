import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UUIDPk, in_check

LEAVE_STATUSES = ("pending", "approved", "rejected", "cancelled")
LEAVE_TYPES = ("sick", "family", "other")


class LeaveRequest(UUIDPk, Timestamps, Base):
    __tablename__ = "leave_requests"
    __table_args__ = (
        CheckConstraint(in_check("status", LEAVE_STATUSES), name="status"),
        CheckConstraint(in_check("leave_type", LEAVE_TYPES), name="leave_type"),
        CheckConstraint("to_date >= from_date", name="dates"),
        Index("ix_leave_student_dates", "student_id", "from_date", "to_date"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    applied_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)
    leave_type: Mapped[str] = mapped_column(String(10), nullable=False, default="other", server_default="other")
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending", server_default="pending")
    decided_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(String(500))
