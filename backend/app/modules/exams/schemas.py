import uuid
from datetime import date, time
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.ops_common.base import Money

Marks = Decimal  # 0..1000 with two decimals, validated by Field below


class ExamCreate(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    exam_type: Literal["monthly", "midterm", "final", "other"]
    academic_year_id: uuid.UUID | None = None  # defaults to the current academic year
    start_date: date
    end_date: date
    status: Literal["draft", "scheduled"] = "draft"

    @model_validator(mode="after")
    def _dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class ExamUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=100)
    exam_type: Literal["monthly", "midterm", "final", "other"] | None = None
    start_date: date | None = None
    end_date: date | None = None
    # results_published can only be set through POST /exams/{id}/publish-results
    status: Literal["draft", "scheduled", "ongoing", "completed"] | None = None


class ExamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    exam_type: str
    academic_year_id: uuid.UUID
    start_date: date
    end_date: date
    status: str


class ScheduleCreate(BaseModel):
    section_id: uuid.UUID
    subject_id: uuid.UUID
    exam_date: date
    start_time: time
    end_time: time
    room: str | None = Field(default=None, max_length=30)
    total_marks: Decimal = Field(gt=0, le=1000, max_digits=6, decimal_places=2)
    passing_marks: Decimal = Field(ge=0, le=1000, max_digits=6, decimal_places=2)

    @model_validator(mode="after")
    def _check(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        if self.passing_marks > self.total_marks:
            raise ValueError("passing_marks cannot exceed total_marks")
        return self


class ScheduleUpdate(BaseModel):
    exam_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    room: str | None = Field(default=None, max_length=30)
    total_marks: Decimal | None = Field(default=None, gt=0, le=1000, max_digits=6, decimal_places=2)
    passing_marks: Decimal | None = Field(default=None, ge=0, le=1000, max_digits=6, decimal_places=2)


class ScheduleOut(BaseModel):
    id: uuid.UUID
    exam_id: uuid.UUID
    section_id: uuid.UUID
    section_name: str | None = None
    subject_id: uuid.UUID
    subject_name: str | None = None
    exam_date: date
    start_time: time
    end_time: time
    room: str | None
    total_marks: Money
    passing_marks: Money


class MarkEntry(BaseModel):
    student_id: uuid.UUID
    marks_obtained: Decimal | None = Field(default=None, ge=0, le=1000, max_digits=6, decimal_places=2)
    is_absent: bool = False
    remarks: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def _either_marks_or_absent(self):
        if self.is_absent and self.marks_obtained is not None:
            raise ValueError("an absent student cannot have marks")
        if not self.is_absent and self.marks_obtained is None:
            raise ValueError("marks_obtained is required unless the student is absent")
        return self


class MarksBulkIn(BaseModel):
    entries: list[MarkEntry] = Field(min_length=1, max_length=200)


class MarkSheetRow(BaseModel):
    student_id: uuid.UUID
    roll_no: str
    student_name: str
    marks_obtained: Money | None
    is_absent: bool
    remarks: str | None


class MarkSheetOut(BaseModel):
    schedule: ScheduleOut
    exam_status: str
    rows: list[MarkSheetRow]


class GradeBand(BaseModel):
    grade: str = Field(min_length=1, max_length=3)
    min_percentage: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    max_percentage: Decimal = Field(ge=0, le=100, max_digits=5, decimal_places=2)
    gpa_points: Decimal | None = Field(default=None, ge=0, le=5, max_digits=3, decimal_places=2)
    remark: str = Field(default="", max_length=50)
    is_pass: bool = True

    @model_validator(mode="after")
    def _range(self):
        if self.max_percentage < self.min_percentage:
            raise ValueError("max_percentage cannot be below min_percentage")
        return self


class GradeBandOut(GradeBand):
    model_config = ConfigDict(from_attributes=True)
    min_percentage: Money
    max_percentage: Money
    gpa_points: Money | None = None


class GradeScaleIn(BaseModel):
    bands: list[GradeBand] = Field(min_length=1, max_length=15)
