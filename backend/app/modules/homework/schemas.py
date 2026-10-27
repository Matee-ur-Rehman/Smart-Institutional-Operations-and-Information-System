import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.modules.ops_common.base import Money


def _clean(value: str | None) -> str | None:
    return value.strip() if isinstance(value, str) else value


class AssignmentCreate(BaseModel):
    section_id: uuid.UUID
    subject_id: uuid.UUID
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    due_date: date
    max_marks: Decimal | None = Field(default=None, gt=0, le=1000, max_digits=6, decimal_places=2)
    status: Literal["draft", "published"] = "published"

    _strip = field_validator("title", "description", mode="before")(_clean)

    @field_validator("due_date")
    @classmethod
    def _not_in_past(cls, value: date) -> date:
        if value < date.today():
            raise ValueError("due_date cannot be in the past")
        return value


class AssignmentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    due_date: date | None = None
    max_marks: Decimal | None = Field(default=None, gt=0, le=1000, max_digits=6, decimal_places=2)
    status: Literal["draft", "published", "closed"] | None = None

    _strip = field_validator("title", "description", mode="before")(_clean)


class AssignmentOut(BaseModel):
    id: uuid.UUID
    teacher_id: uuid.UUID
    teacher_name: str | None = None
    section_id: uuid.UUID
    section_name: str | None = None
    subject_id: uuid.UUID
    subject_name: str | None = None
    title: str
    description: str | None
    assigned_date: date
    due_date: date
    max_marks: Money | None
    has_attachment: bool
    status: str
    created_at: datetime
