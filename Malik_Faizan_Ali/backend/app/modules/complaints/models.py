import uuid

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UUIDPk, in_check

COMPLAINT_CATEGORIES = ("academic", "fee", "teacher", "facility", "transport", "other")
COMPLAINT_KINDS = ("complaint", "feedback", "suggestion")
COMPLAINT_STATUSES = ("open", "in_review", "resolved", "closed")
COMPLAINT_PRIORITIES = ("low", "normal", "high")


class Complaint(UUIDPk, Timestamps, Base):
    __tablename__ = "complaints"
    __table_args__ = (
        CheckConstraint(in_check("category", COMPLAINT_CATEGORIES), name="category"),
        CheckConstraint(in_check("kind", COMPLAINT_KINDS), name="kind"),
        CheckConstraint(in_check("status", COMPLAINT_STATUSES), name="status"),
        CheckConstraint(in_check("priority", COMPLAINT_PRIORITIES), name="priority"),
        Index("ix_complaints_submitter", "submitted_by", "created_at"),
    )

    ticket_no: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    submitted_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    student_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("students.id"))
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="complaint", server_default="complaint")
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", server_default="open")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal", server_default="normal")
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class ComplaintComment(UUIDPk, Timestamps, Base):
    __tablename__ = "complaint_comments"

    complaint_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
