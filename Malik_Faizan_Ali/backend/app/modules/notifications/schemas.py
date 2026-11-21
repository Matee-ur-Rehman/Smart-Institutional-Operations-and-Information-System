import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    body: str
    type: str
    reference_type: str | None = None
    reference_id: uuid.UUID | None = None
    is_read: bool
    read_at: datetime | None = None
    created_at: datetime


class UnreadCount(BaseModel):
    count: int


class DeviceRegister(BaseModel):
    token: str = Field(min_length=10, max_length=500)
    platform: Literal["android", "web"]
