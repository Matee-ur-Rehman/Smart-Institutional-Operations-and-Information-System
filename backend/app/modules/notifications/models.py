import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.ops_common.base import check_in, uuid_pk

NOTIFICATION_TYPES = [
    "announcement", "homework", "marks", "fee", "event", "leave", "attendance", "complaint", "system",
]
PUSH_STATUSES = ["not_sent", "queued", "sent", "failed", "disabled"]


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        check_in("notifications", "type", NOTIFICATION_TYPES),
        check_in("notifications", "push_status", PUSH_STATUSES),
        Index("ix_notifications_user_read", "user_id", "is_read"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(30))
    reference_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    push_status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_sent", server_default="not_sent")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DeviceToken(Base):
    __tablename__ = "device_tokens"
    __table_args__ = (check_in("device_tokens", "platform", ["android", "web"]),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(10), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
