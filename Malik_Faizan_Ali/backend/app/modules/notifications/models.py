import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UUIDPk, in_check

NOTIFICATION_TYPES = ("announcement", "homework", "marks", "fee", "event", "leave", "attendance", "complaint", "system")
PUSH_STATUSES = ("not_sent", "queued", "sent", "failed", "disabled")
DEVICE_PLATFORMS = ("android", "web")


class Notification(UUIDPk, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(in_check("type", NOTIFICATION_TYPES), name="type"),
        CheckConstraint(in_check("push_status", PUSH_STATUSES), name="push_status"),
        Index("ix_notifications_user_created", "user_id", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)
    reference_type: Mapped[str | None] = mapped_column(String(30))
    reference_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    push_status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_sent", server_default="not_sent")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DeviceToken(UUIDPk, Base):
    __tablename__ = "device_tokens"
    __table_args__ = (CheckConstraint(in_check("platform", DEVICE_PLATFORMS), name="platform"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    platform: Mapped[str] = mapped_column(String(10), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
