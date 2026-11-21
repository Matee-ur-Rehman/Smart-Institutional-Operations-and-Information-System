import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["academic", "fee", "teacher", "facility", "transport", "other"]
Kind = Literal["complaint", "feedback", "suggestion"]
CStatus = Literal["open", "in_review", "resolved", "closed"]
CPriority = Literal["low", "normal", "high"]


class ComplaintCreate(BaseModel):
    student_id: uuid.UUID | None = None
    category: Category
    kind: Kind = "complaint"
    subject: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=10, max_length=4000)


class ComplaintUpdate(BaseModel):
    status: CStatus | None = None
    priority: CPriority | None = None
    assigned_to: uuid.UUID | None = None


class CommentCreate(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    is_internal: bool = False


class CommentOut(BaseModel):
    id: uuid.UUID
    author_id: uuid.UUID
    author_name: str | None = None
    author_role: str | None = None
    message: str
    is_internal: bool
    created_at: datetime


class ComplaintOut(BaseModel):
    id: uuid.UUID
    ticket_no: str
    submitted_by: uuid.UUID
    submitted_by_name: str | None = None
    student_id: uuid.UUID | None = None
    student_name: str | None = None
    student_section: str | None = None
    category: str
    kind: str
    subject: str
    description: str
    status: str
    priority: str
    assigned_to: uuid.UUID | None = None
    assigned_to_name: str | None = None
    comment_count: int = 0
    created_at: datetime
    updated_at: datetime
    comments: list[CommentOut] | None = None
