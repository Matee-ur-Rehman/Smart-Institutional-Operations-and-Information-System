import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Frequency = Literal["monthly", "quarterly", "yearly", "one_time"]
Method = Literal["cash", "bank_transfer", "cheque", "other"]
Amount = Field(gt=0, le=10_000_000, decimal_places=2)


class FeeHeadCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    frequency: Frequency


class FeeHeadUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    frequency: Frequency | None = None
    is_active: bool | None = None


class FeeHeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    frequency: str
    is_active: bool


class FeeStructureCreate(BaseModel):
    class_id: uuid.UUID
    fee_head_id: uuid.UUID
    academic_year_id: uuid.UUID | None = None
    amount: Decimal = Amount


class FeeStructureUpdate(BaseModel):
    amount: Decimal = Amount


class FeeStructureOut(BaseModel):
    id: uuid.UUID
    class_id: uuid.UUID
    class_name: str
    fee_head_id: uuid.UUID
    fee_head_name: str
    frequency: str
    academic_year_id: uuid.UUID
    amount: Decimal


class InvoiceItemIn(BaseModel):
    fee_head_id: uuid.UUID
    description: str | None = Field(None, max_length=200)
    amount: Decimal = Amount


class InvoiceCreate(BaseModel):
    student_id: uuid.UUID
    period_label: str = Field(min_length=3, max_length=30)
    issue_date: date | None = None
    due_date: date
    discount_amount: Decimal = Field(Decimal(0), ge=0, decimal_places=2)
    items: list[InvoiceItemIn] | None = Field(None, min_length=1, max_length=20)


class GenerateBody(BaseModel):
    section_id: uuid.UUID | None = None
    class_id: uuid.UUID | None = None
    period_label: str = Field(min_length=3, max_length=30)
    issue_date: date | None = None
    due_date: date
    fee_head_ids: list[uuid.UUID] | None = None

    @model_validator(mode="after")
    def _one_target(self) -> Self:
        if bool(self.section_id) == bool(self.class_id):
            raise ValueError("Provide exactly one of section_id or class_id")
        return self


class PaymentCreate(BaseModel):
    amount: Decimal = Amount
    payment_date: date
    method: Method
    reference: str | None = Field(None, max_length=100)
    remarks: str | None = Field(None, max_length=500)


class ReverseBody(BaseModel):
    reason: str = Field(min_length=5, max_length=500)


class PaymentOut(BaseModel):
    id: uuid.UUID
    receipt_no: str
    invoice_id: uuid.UUID
    amount: Decimal
    payment_date: date
    method: str
    reference: str | None = None
    remarks: str | None = None
    recorded_by_name: str | None = None
    is_reversal: bool
    reversal_of_id: uuid.UUID | None = None
    is_reversed: bool = False
    created_at: datetime


class ItemOut(BaseModel):
    id: uuid.UUID
    fee_head_id: uuid.UUID
    description: str
    amount: Decimal


class InvoiceOut(BaseModel):
    id: uuid.UUID
    invoice_no: str
    student_id: uuid.UUID
    student_name: str | None = None
    roll_no: str | None = None
    section_label: str | None = None
    period_label: str
    issue_date: date
    due_date: date
    total_amount: Decimal
    discount_amount: Decimal
    net_amount: Decimal
    paid_amount: Decimal
    balance: Decimal
    status: str                       # derived: unpaid | partial | paid | overdue | cancelled
    items: list[ItemOut] | None = None
    payments: list[PaymentOut] | None = None
    created_at: datetime
