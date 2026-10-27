import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.access import parent_child_ids
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import require_roles
from app.modules.fees import service
from app.modules.fees.models import FeeHead, FeeInvoice, FeeInvoiceItem, FeePayment, FeeStructure
from app.modules.fees.schemas import (
    FeeHeadCreate, FeeHeadOut, FeeHeadUpdate, FeeStructureCreate, FeeStructureOut, FeeStructureUpdate,
    FeeSummaryOut, GenerateResult, InvoiceCreate, InvoiceDetailOut, InvoiceGenerate, InvoiceOut, PaymentCreate,
    PaymentOut, ReverseIn,
)
from app.modules.notifications.push import dispatch_queued_pushes
from app.modules.ops_common.core_refs import AcademicYear, SchoolClass, Section, Student, User
from app.modules.ops_common.pagination import Page, PageParams, page_of, paginate
from app.modules.ops_common.scope import current_year_id, get_or_404, not_found

router = APIRouter(tags=["Fees"])
ADMIN = Depends(require_roles("admin"))
ADMIN_OR_PARENT = Depends(require_roles("admin", "parent"))


def _allowed_students(user: User, db: Session) -> list[uuid.UUID] | None:
    return None if user.role == "admin" else parent_child_ids(user, db)


def _year_or_400(db: Session, year_id: uuid.UUID | None) -> uuid.UUID:
    if year_id is not None:
        get_or_404(db, AcademicYear, year_id, "Academic year")  # 404, not a database error
        return year_id
    year_id = current_year_id(db)
    if year_id is None:
        raise AppError(400, "bad_request", "No current academic year is set")
    return year_id


# ---------------------------------------------------------------- fee heads
@router.post("/fee-heads", response_model=FeeHeadOut, status_code=201)
def create_fee_head(payload: FeeHeadCreate, db: Session = Depends(get_db), user: User = ADMIN):
    name = payload.name.strip()
    if db.scalar(select(FeeHead.id).where(FeeHead.name == name)) is not None:
        raise AppError(409, "conflict", "A fee head with this name already exists")
    head = FeeHead(name=name, frequency=payload.frequency)
    db.add(head)
    db.commit()
    return head


@router.get("/fee-heads", response_model=list[FeeHeadOut])
def list_fee_heads(db: Session = Depends(get_db), user: User = ADMIN):
    return list(db.scalars(select(FeeHead).order_by(FeeHead.name)))


@router.patch("/fee-heads/{head_id}", response_model=FeeHeadOut)
def update_fee_head(head_id: uuid.UUID, payload: FeeHeadUpdate, db: Session = Depends(get_db), user: User = ADMIN):
    head = get_or_404(db, FeeHead, head_id, "Fee head")
    changes = payload.model_dump(exclude_unset=True)
    new_name = changes.get("name")
    if new_name is not None and db.scalar(
        select(FeeHead.id).where(FeeHead.name == new_name.strip(), FeeHead.id != head.id)
    ) is not None:
        raise AppError(409, "conflict", "A fee head with this name already exists")
    for field, value in changes.items():
        if value is None:
            raise AppError(422, "validation_error", f"{field} cannot be empty")
        setattr(head, field, value.strip() if isinstance(value, str) else value)
    db.commit()
    return head


@router.delete("/fee-heads/{head_id}", status_code=204)
def delete_fee_head(head_id: uuid.UUID, db: Session = Depends(get_db), user: User = ADMIN):
    head = get_or_404(db, FeeHead, head_id, "Fee head")
    in_use = db.scalar(select(FeeStructure.id).where(FeeStructure.fee_head_id == head.id).limit(1)) or db.scalar(
        select(FeeInvoiceItem.id).where(FeeInvoiceItem.fee_head_id == head.id).limit(1)
    )
    if in_use is not None:
        raise AppError(409, "conflict", "This fee head is in use. Deactivate it instead of deleting it")
    db.delete(head)
    db.commit()


# ---------------------------------------------------------------- fee structures
@router.post("/fee-structures", response_model=FeeStructureOut, status_code=201)
def create_fee_structure(payload: FeeStructureCreate, db: Session = Depends(get_db), user: User = ADMIN):
    year_id = _year_or_400(db, payload.academic_year_id)
    get_or_404(db, SchoolClass, payload.class_id, "Class")
    get_or_404(db, FeeHead, payload.fee_head_id, "Fee head")
    exists = db.scalar(
        select(FeeStructure.id).where(
            FeeStructure.class_id == payload.class_id, FeeStructure.fee_head_id == payload.fee_head_id,
            FeeStructure.academic_year_id == year_id,
        )
    )
    if exists is not None:
        raise AppError(409, "conflict", "This class already has an amount for this fee head in this year")
    row = FeeStructure(class_id=payload.class_id, fee_head_id=payload.fee_head_id, academic_year_id=year_id, amount=payload.amount)
    db.add(row)
    db.commit()
    return row


@router.get("/fee-structures", response_model=list[FeeStructureOut])
def list_fee_structures(
    class_id: uuid.UUID | None = None, academic_year_id: uuid.UUID | None = None,
    db: Session = Depends(get_db), user: User = ADMIN,
):
    stmt = select(FeeStructure)
    if class_id:
        stmt = stmt.where(FeeStructure.class_id == class_id)
    if academic_year_id:
        stmt = stmt.where(FeeStructure.academic_year_id == academic_year_id)
    return list(db.scalars(stmt))


@router.patch("/fee-structures/{structure_id}", response_model=FeeStructureOut)
def update_fee_structure(structure_id: uuid.UUID, payload: FeeStructureUpdate, db: Session = Depends(get_db), user: User = ADMIN):
    row = get_or_404(db, FeeStructure, structure_id, "Fee structure")
    row.amount = payload.amount  # existing invoices keep the amount they were issued with
    db.commit()
    return row


@router.delete("/fee-structures/{structure_id}", status_code=204)
def delete_fee_structure(structure_id: uuid.UUID, db: Session = Depends(get_db), user: User = ADMIN):
    db.delete(get_or_404(db, FeeStructure, structure_id, "Fee structure"))
    db.commit()


# ---------------------------------------------------------------- invoices
@router.post("/fee-invoices", response_model=InvoiceDetailOut, status_code=201)
def create_invoice(payload: InvoiceCreate, background: BackgroundTasks, db: Session = Depends(get_db), user: User = ADMIN):
    student = db.scalar(select(Student).where(Student.id == payload.student_id, Student.is_active.is_(True)))
    if student is None:
        raise not_found("Student")
    year_id = _year_or_400(db, payload.academic_year_id)
    if payload.items is not None:
        for item in payload.items:
            if item.fee_head_id is not None:
                get_or_404(db, FeeHead, item.fee_head_id, "Fee head")
        lines = [(i.fee_head_id, i.description.strip(), Decimal(i.amount)) for i in payload.items]
    else:
        class_id = db.scalar(select(Section.class_id).where(Section.id == student.section_id))
        found = service.structure_items(db, class_id, year_id, None)
        if not found:
            raise AppError(400, "bad_request", "The class has no monthly fee structure; send items explicitly")
        lines = [(head.id, head.name, amount) for head, amount in found]
    duplicate = db.scalar(
        select(FeeInvoice.id).where(
            FeeInvoice.student_id == student.id, FeeInvoice.period_label == payload.period_label, FeeInvoice.status != "cancelled"
        )
    )
    if duplicate is not None:
        raise AppError(409, "conflict", "This student already has an invoice for this period")
    invoice = service.create_invoice(db, student, year_id, payload.period_label, payload.due_date, lines, Decimal(payload.discount_amount))
    db.commit()
    if settings.fcm_enabled:
        background.add_task(dispatch_queued_pushes)
    return service.to_invoice_detail(db, service.get_invoice_row(db, invoice.id, None))


@router.post("/fee-invoices/generate", response_model=GenerateResult)
def generate_invoices(payload: InvoiceGenerate, background: BackgroundTasks, db: Session = Depends(get_db), user: User = ADMIN):
    year_id = _year_or_400(db, payload.academic_year_id)
    if payload.section_id is not None:
        get_or_404(db, Section, payload.section_id, "Section")
    else:
        get_or_404(db, SchoolClass, payload.class_id, "Class")
    stmt = (
        select(Student, Section.class_id)
        .join(Section, Section.id == Student.section_id)
        .where(Student.is_active.is_(True))
    )
    stmt = stmt.where(Section.id == payload.section_id) if payload.section_id else stmt.where(Section.class_id == payload.class_id)
    students = db.execute(stmt).all()
    existing = set(
        db.scalars(
            select(FeeInvoice.student_id).where(
                FeeInvoice.period_label == payload.period_label, FeeInvoice.status != "cancelled",
                FeeInvoice.student_id.in_([s.id for s, _ in students] or [uuid.uuid4()]),
            )
        )
    )
    cache: dict[uuid.UUID, list] = {}
    created = skipped_existing = skipped_no_structure = 0
    for student, class_id in students:
        if student.id in existing:
            skipped_existing += 1
            continue
        if class_id not in cache:
            cache[class_id] = service.structure_items(db, class_id, year_id, payload.fee_head_ids)
        found = cache[class_id]
        if not found:
            skipped_no_structure += 1
            continue
        lines = [(head.id, head.name, amount) for head, amount in found]
        service.create_invoice(db, student, year_id, payload.period_label, payload.due_date, lines, Decimal("0"))
        created += 1
    db.commit()
    if settings.fcm_enabled:
        background.add_task(dispatch_queued_pushes)
    return GenerateResult(created=created, skipped_existing=skipped_existing, skipped_no_fee_structure=skipped_no_structure)


@router.get("/fee-invoices", response_model=Page[InvoiceOut])
def list_invoices(
    student_id: uuid.UUID | None = None,
    status: str | None = Query(None, pattern="^(unpaid|partial|paid|overdue|cancelled)$"),
    period_label: str | None = None,
    section_id: uuid.UUID | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    params: PageParams = Depends(),
    db: Session = Depends(get_db),
    user: User = ADMIN_OR_PARENT,
):
    allowed = _allowed_students(user, db)
    stmt = service.invoice_query()
    if allowed is not None:
        stmt = stmt.where(FeeInvoice.student_id.in_(allowed))
    if student_id is not None:
        if allowed is not None and student_id not in allowed:
            raise not_found("Student")
        stmt = stmt.where(FeeInvoice.student_id == student_id)
    today = date.today()
    if status == "overdue":
        stmt = stmt.where(FeeInvoice.status.in_(["unpaid", "partial"]), FeeInvoice.due_date < today)
    elif status in ("unpaid", "partial"):
        stmt = stmt.where(FeeInvoice.status == status, FeeInvoice.due_date >= today)
    elif status:
        stmt = stmt.where(FeeInvoice.status == status)
    if period_label:
        stmt = stmt.where(FeeInvoice.period_label == period_label)
    if section_id:
        stmt = stmt.where(Section.id == section_id)
    if due_from:
        stmt = stmt.where(FeeInvoice.due_date >= due_from)
    if due_to:
        stmt = stmt.where(FeeInvoice.due_date <= due_to)
    rows, total = paginate(db, stmt.order_by(FeeInvoice.due_date.desc(), FeeInvoice.invoice_no), params, scalars=False)
    return page_of([service.to_invoice_out(r) for r in rows], total, params)


@router.get("/fee-invoices/{invoice_id}", response_model=InvoiceDetailOut)
def get_invoice(invoice_id: uuid.UUID, db: Session = Depends(get_db), user: User = ADMIN_OR_PARENT):
    return service.to_invoice_detail(db, service.get_invoice_row(db, invoice_id, _allowed_students(user, db)))


@router.post("/fee-invoices/{invoice_id}/payments", response_model=PaymentOut, status_code=201)
def add_payment(
    invoice_id: uuid.UUID, payload: PaymentCreate, background: BackgroundTasks,
    db: Session = Depends(get_db), user: User = ADMIN,
):
    payment = service.record_payment(
        db, invoice_id, user, Decimal(payload.amount), payload.payment_date, payload.method, payload.reference, payload.remarks
    )
    db.commit()
    if settings.fcm_enabled:
        background.add_task(dispatch_queued_pushes)
    return payment


@router.post("/fee-payments/{payment_id}/reverse", response_model=PaymentOut, status_code=201)
def reverse_payment(payment_id: uuid.UUID, payload: ReverseIn, db: Session = Depends(get_db), user: User = ADMIN):
    reversal = service.reverse_payment(db, payment_id, user, payload.reason.strip())
    db.commit()
    return reversal


@router.post("/fee-invoices/{invoice_id}/cancel", response_model=InvoiceOut)
def cancel_invoice(invoice_id: uuid.UUID, db: Session = Depends(get_db), user: User = ADMIN):
    invoice = get_or_404(db, FeeInvoice, invoice_id, "Invoice")
    if db.scalar(select(FeePayment.id).where(FeePayment.invoice_id == invoice.id).limit(1)) is not None:
        raise AppError(409, "conflict", "Invoices that have payments cannot be cancelled")
    invoice.status = "cancelled"
    db.commit()
    return service.to_invoice_out(service.get_invoice_row(db, invoice.id, None))


# ---------------------------------------------------------------- reporting
@router.get("/fee-summary", response_model=FeeSummaryOut)
def fee_summary(
    class_id: uuid.UUID | None = None, section_id: uuid.UUID | None = None, period_label: str | None = None,
    db: Session = Depends(get_db), user: User = ADMIN,
):
    return service.summary(db, class_id, section_id, period_label)


@router.get("/students/{student_id}/fee-statement")
def fee_statement(student_id: uuid.UUID, db: Session = Depends(get_db), user: User = ADMIN_OR_PARENT):
    allowed = _allowed_students(user, db)
    if allowed is not None and student_id not in allowed:
        raise not_found("Student")
    data = service.get_fee_statement_data(db, student_id)
    # Same JSON shape the PDF code receives, made JSON-friendly (money as numbers).
    from fastapi.encoders import jsonable_encoder

    return jsonable_encoder(data, custom_encoder={Decimal: float})
