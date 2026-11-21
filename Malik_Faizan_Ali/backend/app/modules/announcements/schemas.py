import uuid
from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Audience = Literal["all", "teachers", "students", "parents", "class"]
Priority = Literal["normal", "important", "urgent"]
AStatus = Literal["draft", "published", "archived"]


class AnnouncementCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=1, max_length=5000)
    audience: Audience = "all"
    class_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    priority: Priority = "normal"
    publish_at: datetime | None = None
    expires_at: datetime | None = None
    status: Literal["draft", "published"] = "published"

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.audience == "class" and not (self.class_id or self.section_id):
            raise ValueError("class_id or section_id is required when audience is 'class'")
        if self.publish_at and self.expires_at and self.expires_at <= self.publish_at:
            raise ValueError("expires_at must be after publish_at")
        return self


class AnnouncementUpdate(BaseModel):
    title: str | None = Field(None, min_length=3, max_length=200)
    body: str | None = Field(None, min_length=1, max_length=5000)
    audience: Audience | None = None
    class_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    priority: Priority | None = None
    publish_at: datetime | None = None
    expires_at: datetime | None = None
    status: Literal["draft", "published"] | None = None


class AnnouncementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    body: str
    audience: str
    class_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    target_label: str
    priority: str
    publish_at: datetime
    expires_at: datetime | None = None
    status: str
    is_expired: bool
    created_by: uuid.UUID
    created_by_name: str | None = None
    created_at: datetime
