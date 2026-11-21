import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UUIDPk, in_check

AUDIENCES = ("all", "teachers", "students", "parents", "class")
PRIORITIES = ("normal", "important", "urgent")
ANNOUNCEMENT_STATUSES = ("draft", "published", "archived")


class Announcement(UUIDPk, Timestamps, Base):
    __tablename__ = "announcements"
    __table_args__ = (
        CheckConstraint(in_check("audience", AUDIENCES), name="audience"),
        CheckConstraint(in_check("priority", PRIORITIES), name="priority"),
        CheckConstraint(in_check("status", ANNOUNCEMENT_STATUSES), name="status"),
        CheckConstraint("audience <> 'class' OR class_id IS NOT NULL OR section_id IS NOT NULL", name="class_target"),
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[str] = mapped_column(String(20), nullable=False, default="all")
    class_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("classes.id"))
    section_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sections.id"))
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal", server_default="normal")
    publish_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", server_default="draft")
    # additive column (Member 2): set once the notification fan-out has been done
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
