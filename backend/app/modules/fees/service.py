import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.fees.models import FeeHead, FeeInvoice, FeeInvoiceItem, FeePayment, FeeStructure
from app.modules.fees.schemas import InvoiceDetailOut, InvoiceOut, ItemOut, PaymentOut
from app.modules.notifications.service import notify_users, parent_user_ids
from app.modules.ops_common.core_refs import SchoolClass, Section, Student, User
from app.modules.ops_common.scope import not_found

ZERO = Decimal("0.00")


def new_number(prefix: str) -> str:
    return f"{prefix}-{date.today():%Y%m}-{uuid.uuid4().hex[:8].upper()}"


def net_of(invoice: FeeInvoice) -> Decimal:
    return Decimal(invoice.total_amount) - Decimal(invoice.discount_amount)


def balance_of(invoice: FeeInvoice) -> Decimal:
    return net_of(invoice) - Decimal(invoice.paid_amount)


def stored_status(invoice: FeeInvoice) -> str:
    if invoice.status == "cancelled":
        return "cancelled"
    paid = Decimal(invoice.paid_amount)
    if paid >= net_of(invoice):
        return "paid"
    return "partial" if paid > 0 else "unpaid"


def effective_status(invoice: FeeInvoice, today: date | None = None) -> str:
    """'overdue' is derived at read time so no scheduled job is needed."""
    status = invoice.status
    if status in ("unpaid", "partial") and invoice.due_date < (today or date.today()):
        return "overdue"
    return status


def invoice_query():
    return (
        select(FeeInvoice, Student.full_name, Student.roll_no, SchoolClass.name, Section.name)
        .join(Student, Student.id == FeeInvoice.student_id)
        .join(Section, Section.id == Student.section_id)
        .join(SchoolClass, SchoolClass.id == Section.class_id)
    )


def to_invoice_out(row) -> InvoiceOut:
    invoice, student_name, roll_no, class_name, section_name = row
    return InvoiceOut(
        id=invoice.id, invoice_no=invoice.invoice_no, student_id=invoice.student_id, student_name=student_name,
        roll_no=roll_no, section_name=f"{class_name}-{section_name}", period_label=invoice.period_label,
        issue_date=invoice.issue_date, due_date=invoice.due_date, total_amount=invoice.total_amount,
        discount_amount=invoice.discount_amount, net_amount=net_of(invoice), paid_amount=invoice.paid_amount,
        balance=balance_of(invoice), status=effective_status(invoice),
    )


def to_invoice_detail(db: Session, row) -> InvoiceDetailOut:
    base = to_invoice_out(row)
    invoice = row[0]
    items = list(db.scalars(select(FeeInvoiceItem).where(FeeInvoiceItem.invoice_id == invoice.id)))
    payments = list(
        db.scalars(select(FeePayment).where(FeePayment.invoice_id == invoice.id).order_by(FeePayment.created_at))
    )
    return InvoiceDetailOut(
        **base.model_dump(),
        items=[ItemOut.model_validate(i) for i in items],
        payments=[PaymentOut.model_validate(p) for p in payments],
    )


def get_invoice_row(db: Session, invoice_id: uuid.UUID, allowed_student_ids: list[uuid.UUID] | None):
    """allowed_student_ids=None means unrestricted (admin). Anyone else only reaches their own children."""
    stmt = invoice_query().where(FeeInvoice.id == invoice_id)
    if allowed_student_ids is not None:
        stmt = stmt.where(FeeInvoice.student_id.in_(allowed_student_ids))
    row = db.execute(stmt).first()
    if row is None:
        raise not_found("Invoice")
    return row


def structure_items(
    db: Session, class_id: uuid.UUID, year_id: uuid.UUID, fee_head_ids: list[uuid.UUID] | None
) -> list[tuple[FeeHead, Decimal]]:
    stmt = (
        select(FeeHead, FeeStructure.amount)
        .join(FeeStructure, FeeStructure.fee_head_id == FeeHead.id)
        .where(FeeStructure.class_id == class_id, FeeStructure.academic_year_id == year_id, FeeHead.is_active.is_(True))
        .order_by(FeeHead.name)
    )
    if fee_head_ids:
        stmt = stmt.where(FeeHead.id.in_(fee_head_ids))
    else:
        stmt = stmt.where(FeeHead.frequency == "monthly")
    return [(head, Decimal(amount)) for head, amount in db.execute(stmt).all()]


def create_invoice(
    db: Session, student: Student, year_id: uuid.UUID, period_label: str, due_date: date,
    lines: list[tuple[uuid.UUID | None, str, Decimal]], discount: Decimal,
) -> FeeInvoice:
    total = sum((amount for _, _, amount in lines), ZERO)
    if discount > total:
        raise AppError(400, "bad_request", "Discount cannot be more than the invoice total")
    invoice = FeeInvoice(
        invoice_no=new_number("INV"), student_id=student.id, academic_year_id=year_id, period_label=period_label,
        issue_date=date.today(), due_date=due_date, total_amount=total, discount_amount=discount,
        paid_amount=ZERO, status="unpaid",
    )
    if total - discount <= 0:  # fully discounted: nothing to collect
        invoice.status = "paid"
    db.add(invoice)
    db.flush()
    db.add_all(
        FeeInvoiceItem(invoice_id=invoice.id, fee_head_id=head_id, description=description, amount=amount)
        for head_id, description, amount in lines
    )
    db.flush()
    notify_users(
        db, parent_user_ids(db, [student.id]), title=f"Fee invoice: {period_label}",
        body=f"A fee invoice of PKR {total - discount:,.2f} is due on {due_date.isoformat()}.",
        type="fee", reference_type="fee_invoice", reference_id=invoice.id,
    )
    return invoice


def record_payment(db: Session, invoice_id: uuid.UUID, user: User, amount: Decimal, payment_date: date,
                   method: str, reference: str | None, remarks: str | None) -> FeePayment:
    invoice = db.scalar(select(FeeInvoice).where(FeeInvoice.id == invoice_id).with_for_update())
    if invoice is None:
        raise not_found("Invoice")
    if invoice.status == "cancelled":
        raise AppError(409, "conflict", "This invoice is cancelled")
    balance = balance_of(invoice)
    if amount > balance:
        raise AppError(400, "bad_request", f"Amount exceeds the outstanding balance of {balance:,.2f}")
    payment = FeePayment(
        receipt_no=new_number("RCT"), invoice_id=invoice.id, amount=amount, payment_date=payment_date,
        method=method, reference=reference, recorded_by=user.id, remarks=remarks,
    )
    db.add(payment)
    invoice.paid_amount = Decimal(invoice.paid_amount) + amount
    invoice.status = stored_status(invoice)
    db.flush()
    notify_users(
        db, parent_user_ids(db, [invoice.student_id]), title="Fee payment received",
        body=f"PKR {amount:,.2f} received for {invoice.period_label} (receipt {payment.receipt_no}).",
        type="fee", reference_type="fee_payment", reference_id=payment.id,
    )
    return payment


def reverse_payment(db: Session, payment_id: uuid.UUID, user: User, reason: str) -> FeePayment:
    original = db.get(FeePayment, payment_id)
    if original is None:
        raise not_found("Payment")
    if original.is_reversal:
        raise AppError(409, "conflict", "A reversal cannot itself be reversed")
    if db.scalar(select(FeePayment.id).where(FeePayment.reverses_payment_id == original.id)) is not None:
        raise AppError(409, "conflict", "This payment has already been reversed")
    invoice = db.scalar(select(FeeInvoice).where(FeeInvoice.id == original.invoice_id).with_for_update())
    reversal = FeePayment(
        receipt_no=new_number("REV"), invoice_id=invoice.id, amount=original.amount, payment_date=date.today(),
        method=original.method, recorded_by=user.id, remarks=reason, is_reversal=True,
        reverses_payment_id=original.id,
    )
    db.add(reversal)
    invoice.paid_amount = Decimal(invoice.paid_amount) - Decimal(original.amount)
    invoice.status = stored_status(invoice)
    db.flush()
    return reversal


def summary(db: Session, class_id=None, section_id=None, period_label=None) -> dict:
    net = FeeInvoice.total_amount - FeeInvoice.discount_amount
    today = date.today()
    stmt = (
        select(
            func.count(FeeInvoice.id),
            func.coalesce(func.sum(net), 0),
            func.coalesce(func.sum(FeeInvoice.paid_amount), 0),
            func.coalesce(
                func.sum(case((and_(FeeInvoice.due_date < today, net > FeeInvoice.paid_amount), net - FeeInvoice.paid_amount), else_=0)),
                0,
            ),
        )
        .join(Student, Student.id == FeeInvoice.student_id)
        .join(Section, Section.id == Student.section_id)
        .where(FeeInvoice.status != "cancelled")
    )
    if class_id:
        stmt = stmt.where(Section.class_id == class_id)
    if section_id:
        stmt = stmt.where(Section.id == section_id)
    if period_label:
        stmt = stmt.where(FeeInvoice.period_label == period_label)
    count, billed, collected, overdue = db.execute(stmt).one()
    def money(value) -> Decimal:  # SQLite returns float sums; going via str avoids 0.1+0.2 style artefacts
        return Decimal(str(value)).quantize(Decimal("0.01"))

    billed, collected, overdue = money(billed), money(collected), money(overdue)
    return {
        "billed": billed, "collected": collected, "outstanding": billed - collected,
        "overdue": overdue, "invoice_count": count,
    }


# ---- PDF data functions for Member 1 (docs/API_CONTRACT.md section 5). Authorization is the caller's job.
def get_fee_statement_data(db: Session, student_id: uuid.UUID) -> dict:
    student_row = db.execute(
        select(Student, SchoolClass.name, Section.name)
        .join(Section, Section.id == Student.section_id)
        .join(SchoolClass, SchoolClass.id == Section.class_id)
        .where(Student.id == student_id)
    ).first()
    if student_row is None:
        raise not_found("Student")
    student, class_name, section_name = student_row
    rows = db.execute(invoice_query().where(FeeInvoice.student_id == student_id).order_by(FeeInvoice.issue_date.desc())).all()
    invoices = [to_invoice_detail(db, row) for row in rows if row[0].status != "cancelled"]
    billed = sum((i.net_amount for i in invoices), ZERO)
    paid = sum((i.paid_amount for i in invoices), ZERO)
    return {
        "student": {"id": student.id, "name": student.full_name, "roll_no": student.roll_no,
                    "class_name": class_name, "section_name": section_name},
        "invoices": [i.model_dump() for i in invoices],
        "totals": {"billed": billed, "paid": paid, "outstanding": billed - paid},
    }


def get_fee_receipt_data(db: Session, payment_id: uuid.UUID) -> dict:
    payment = db.get(FeePayment, payment_id)
    if payment is None:
        raise not_found("Payment")
    row = db.execute(invoice_query().where(FeeInvoice.id == payment.invoice_id)).first()
    invoice = to_invoice_out(row)
    return {
        "receipt": PaymentOut.model_validate(payment).model_dump(),
        "invoice": invoice.model_dump(),
    }
