import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.ops_common.base import TimestampMixin, check_in, uuid_pk

CATEGORIES = ["academic", "fee", "teacher", "facility", "transport", "other"]
KINDS = ["complaint", "feedback", "suggestion"]
STATUSES = ["open", "in_review", "resolved", "closed"]
PRIORITIES = ["low", "normal", "high"]


class Complaint(TimestampMixin, Base):
    __tablename__ = "complaints"
    __table_args__ = (
        check_in("complaints", "category", CATEGORIES),
        check_in("complaints", "kind", KINDS),
        check_in("complaints", "status", STATUSES),
        check_in("complaints", "priority", PRIORITIES),
        Index("ix_complaints_submitted_by", "submitted_by"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    ticket_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    submitted_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    student_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("students.id"))
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="complaint")
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"))


class ComplaintComment(TimestampMixin, Base):
    __tablename__ = "complaint_comments"

    id: Mapped[uuid.UUID] = uuid_pk()
    complaint_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("complaints.id"), nullable=False, index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
