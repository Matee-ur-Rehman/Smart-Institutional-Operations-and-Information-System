import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.ops_common.base import TimestampMixin, check_in, uuid_pk

AUDIENCES = ["all", "teachers", "students", "parents", "class"]
PRIORITIES = ["normal", "important", "urgent"]
STATUSES = ["draft", "published", "archived"]


class Announcement(TimestampMixin, Base):
    __tablename__ = "announcements"
    __table_args__ = (
        check_in("announcements", "audience", AUDIENCES),
        check_in("announcements", "priority", PRIORITIES),
        check_in("announcements", "status", STATUSES),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[str] = mapped_column(String(20), nullable=False, default="all")
    class_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("classes.id"))
    section_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("sections.id"))
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
