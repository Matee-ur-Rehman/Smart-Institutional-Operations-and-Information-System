import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.ops_common.base import TimestampMixin, check_in, uuid_pk

FEE_FREQUENCIES = ["monthly", "quarterly", "yearly", "one_time"]
# "overdue" is a CHECK-legal value but is never stored: it is derived when invoices are read.
INVOICE_STATUSES = ["unpaid", "partial", "paid", "overdue", "cancelled"]
PAYMENT_METHODS = ["cash", "bank_transfer", "cheque", "other"]


class FeeHead(TimestampMixin, Base):
    __tablename__ = "fee_heads"
    __table_args__ = (check_in("fee_heads", "frequency", FEE_FREQUENCIES),)

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class FeeStructure(TimestampMixin, Base):
    __tablename__ = "fee_structures"
    __table_args__ = (
        UniqueConstraint("class_id", "fee_head_id", "academic_year_id"),
        CheckConstraint("amount > 0", name="ck_fee_structures_amount"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    class_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("classes.id"), nullable=False)
    fee_head_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("fee_heads.id"), nullable=False)
    academic_year_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("academic_years.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)


class FeeInvoice(TimestampMixin, Base):
    __tablename__ = "fee_invoices"
    __table_args__ = (
        check_in("fee_invoices", "status", INVOICE_STATUSES),
        CheckConstraint("discount_amount >= 0 AND discount_amount <= total_amount", name="ck_fee_invoices_discount"),
        CheckConstraint("paid_amount >= 0", name="ck_fee_invoices_paid"),
        Index("ix_fee_invoices_student_period", "student_id", "period_label"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    invoice_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    student_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("students.id"), nullable=False, index=True)
    academic_year_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("academic_years.id"), nullable=False)
    period_label: Mapped[str] = mapped_column(String(30), nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="unpaid")


class FeeInvoiceItem(Base):
    __tablename__ = "fee_invoice_items"
    __table_args__ = (CheckConstraint("amount > 0", name="ck_fee_invoice_items_amount"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("fee_invoices.id"), nullable=False, index=True)
    fee_head_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("fee_heads.id"))
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)


class FeePayment(TimestampMixin, Base):
    """Append-only. A mistaken payment is undone by a reversal row (is_reversal=True), never edited."""

    __tablename__ = "fee_payments"
    __table_args__ = (
        check_in("fee_payments", "method", PAYMENT_METHODS),
        CheckConstraint("amount > 0", name="ck_fee_payments_amount"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    receipt_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("fee_invoices.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_date: Mapped[date] = mapped_column(Date, nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(100))
    recorded_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text)
    is_reversal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    reverses_payment_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("fee_payments.id"))
