import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AssignmentCreate(BaseModel):
    section_id: uuid.UUID
    subject_id: uuid.UUID
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(None, max_length=5000)
    due_date: date
    max_marks: Decimal | None = Field(None, gt=0, le=9999, decimal_places=2)
    status: Literal["draft", "published"] = "published"


class AssignmentUpdate(BaseModel):
    title: str | None = Field(None, min_length=3, max_length=200)
    description: str | None = Field(None, max_length=5000)
    due_date: date | None = None
    max_marks: Decimal | None = Field(None, gt=0, le=9999, decimal_places=2)
    status: Literal["draft", "published", "closed"] | None = None


class AssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    teacher_id: uuid.UUID
    teacher_name: str | None = None
    section_id: uuid.UUID
    section_label: str | None = None
    subject_id: uuid.UUID
    subject_name: str | None = None
    title: str
    description: str | None = None
    assigned_date: date
    due_date: date
    max_marks: Decimal | None = None
    has_attachment: bool
    status: str
    is_overdue: bool
    days_left: int
    created_at: datetime
