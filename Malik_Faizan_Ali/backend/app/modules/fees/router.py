import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.common.pagination import Page, PageParams, page_params, paginate
from app.common.scope import (
    current_year_id, linked_child, parent_user_ids_of_student, section_labels,
)
from app.common.timeutil import school_today
from app.core.access import can_access_student, parent_child_ids
from app.core.database import get_db
from app.core.errors import BadRequest, Conflict, NotFound, ValidationFailed, field_error
from app.core.security import get_current_user, require_roles
from app.modules.fees import service
from app.modules.fees.models import FeeHead, FeeInvoice, FeeInvoiceItem, FeePayment, FeeStructure
from app.modules.fees.schemas import (
    FeeHeadCreate, FeeHeadOut, FeeHeadUpdate, FeeStructureCreate, FeeStructureOut, FeeStructureUpdate, GenerateBody,
    InvoiceCreate, InvoiceOut, PaymentCreate, PaymentOut, ReverseBody,
)
from app.modules.foundation.models import AcademicYear, SchoolClass, Section, Student, User
from app.modules.notifications.service import notify_users

router = APIRouter(tags=["Fees"])
admin_only = Depends(require_roles("admin"))
admin_parent = Depends(require_roles("admin", "parent"))
ZERO = Decimal("0.00")


# ============================================================ fee heads
@router.post("/fee-heads", response_model=FeeHeadOut, status_code=201)
def create_head(body: FeeHeadCreate, user: User = admin_only, db: Session = Depends(get_db)):
    if db.scalar(select(FeeHead.id).where(func.lower(FeeHead.name) == body.name.strip().lower())):
        raise Conflict("A fee head with this name already exists")
    h = FeeHead(name=body.name.strip(), frequency=body.frequency)
    db.add(h)
    db.commit()
    return h


@router.get("/fee-heads", response_model=list[FeeHeadOut])
def list_heads(active_only: bool = False, user: User = admin_only, db: Session = Depends(get_db)):
    stmt = select(FeeHead).order_by(FeeHead.name)
    if active_only:
        stmt = stmt.where(FeeHead.is_active)
    return list(db.scalars(stmt))


def _head(db: Session, head_id: uuid.UUID) -> FeeHead:
    h = db.get(FeeHead, head_id)
    if h is None:
        raise NotFound("Fee head not found")
    return h


@router.get("/fee-heads/{head_id}", response_model=FeeHeadOut)
def get_head(head_id: uuid.UUID, user: User = admin_only, db: Session = Depends(get_db)):
    return _head(db, head_id)


@router.patch("/fee-heads/{head_id}", response_model=FeeHeadOut)
def update_head(head_id: uuid.UUID, body: FeeHeadUpdate, user: User = admin_only, db: Session = Depends(get_db)):
    h = _head(db, head_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("name") and db.scalar(select(FeeHead.id).where(func.lower(FeeHead.name) == data["name"].strip().lower(),
                                                              FeeHead.id != h.id)):
        raise Conflict("A fee head with this name already exists")
    for k, v in data.items():
        if v is not None:
            setattr(h, k, v.strip() if k == "name" else v)
    db.commit()
    return h


@router.delete("/fee-heads/{head_id}", status_code=204)
def delete_head(head_id: uuid.UUID, user: User = admin_only, db: Session = Depends(get_db)):
    h = _head(db, head_id)
    used = db.scalar(select(FeeStructure.id).where(FeeStructure.fee_head_id == h.id).limit(1)) or \
        db.scalar(select(FeeInvoiceItem.id).where(FeeInvoiceItem.fee_head_id == h.id).limit(1))
    if used:
        raise Conflict("This fee head is in use. Deactivate it instead of deleting it.", code="in_use")
    db.delete(h)
    db.commit()


# ============================================================ fee structures
def _structure_out(db: Session, rows: list[FeeStructure]) -> list[FeeStructureOut]:
    cls = {c.id: c.name for c in db.scalars(select(SchoolClass).where(SchoolClass.id.in_({r.class_id for r in rows})))} if rows else {}
    heads = {h.id: h for h in db.scalars(select(FeeHead).where(FeeHead.id.in_({r.fee_head_id for r in rows})))} if rows else {}
    return [FeeStructureOut(id=r.id, class_id=r.class_id, class_name=cls.get(r.class_id, ""), fee_head_id=r.fee_head_id,
                            fee_head_name=heads[r.fee_head_id].name, frequency=heads[r.fee_head_id].frequency,
                            academic_year_id=r.academic_year_id, amount=r.amount) for r in rows]


@router.post("/fee-structures", response_model=FeeStructureOut, status_code=201)
def create_structure(body: FeeStructureCreate, user: User = admin_only, db: Session = Depends(get_db)):
    year_id = body.academic_year_id or current_year_id(db)
    errors = []
    if db.get(SchoolClass, body.class_id) is None:
        errors.append(field_error("class_id", "Class does not exist"))
    if db.get(FeeHead, body.fee_head_id) is None:
        errors.append(field_error("fee_head_id", "Fee head does not exist"))
    if db.get(AcademicYear, year_id) is None:
        errors.append(field_error("academic_year_id", "Academic year does not exist"))
    if errors:
        raise ValidationFailed(errors=errors)
    if db.scalar(select(FeeStructure.id).where(FeeStructure.class_id == body.class_id,
                 FeeStructure.fee_head_id == body.fee_head_id, FeeStructure.academic_year_id == year_id)):
        raise Conflict("This class already has an amount for this fee head and year")
    s = FeeStructure(class_id=body.class_id, fee_head_id=body.fee_head_id, academic_year_id=year_id, amount=body.amount)
    db.add(s)
    db.commit()
    return _structure_out(db, [s])[0]


@router.get("/fee-structures", response_model=list[FeeStructureOut])
def list_structures(class_id: uuid.UUID | None = None, academic_year_id: uuid.UUID | None = None,
                    user: User = admin_only, db: Session = Depends(get_db)):
    stmt = select(FeeStructure).join(SchoolClass, SchoolClass.id == FeeStructure.class_id).join(
        FeeHead, FeeHead.id == FeeStructure.fee_head_id)
    if class_id:
        stmt = stmt.where(FeeStructure.class_id == class_id)
    stmt = stmt.where(FeeStructure.academic_year_id == (academic_year_id or current_year_id(db)))
    return _structure_out(db, list(db.scalars(stmt.order_by(SchoolClass.grade_level, FeeHead.name))))


def _structure(db: Session, sid: uuid.UUID) -> FeeStructure:
    s = db.get(FeeStructure, sid)
    if s is None:
        raise NotFound("Fee structure not found")
    return s


@router.get("/fee-structures/{structure_id}", response_model=FeeStructureOut)
def get_structure(structure_id: uuid.UUID, user: User = admin_only, db: Session = Depends(get_db)):
    return _structure_out(db, [_structure(db, structure_id)])[0]


@router.patch("/fee-structures/{structure_id}", response_model=FeeStructureOut)
def update_structure(structure_id: uuid.UUID, body: FeeStructureUpdate, user: User = admin_only, db: Session = Depends(get_db)):
    s = _structure(db, structure_id)
    s.amount = body.amount  # existing invoices keep the amount they were issued with
    db.commit()
    return _structure_out(db, [s])[0]


@router.delete("/fee-structures/{structure_id}", status_code=204)
def delete_structure(structure_id: uuid.UUID, user: User = admin_only, db: Session = Depends(get_db)):
    db.delete(_structure(db, structure_id))
    db.commit()


# ============================================================ invoices
def _structure_items(db: Session, class_id: uuid.UUID, year_id: uuid.UUID, head_ids: list[uuid.UUID] | None):
    stmt = select(FeeStructure, FeeHead).join(FeeHead, FeeHead.id == FeeStructure.fee_head_id).where(
        FeeStructure.class_id == class_id, FeeStructure.academic_year_id == year_id, FeeHead.is_active)
    stmt = stmt.where(FeeHead.id.in_(head_ids)) if head_ids else stmt.where(FeeHead.frequency == "monthly")
    return [(s, h) for s, h in db.execute(stmt.order_by(FeeHead.name)).all()]


def _class_of_student(db: Session, st: Student) -> uuid.UUID:
    return db.scalar(select(Section.class_id).where(Section.id == st.section_id))


def _new_invoice(db: Session, st: Student, year_id, period, issue, due, items: list[tuple], discount: Decimal) -> FeeInvoice:
    total = sum((a for _, _, a in items), ZERO)
    inv = FeeInvoice(invoice_no=service.next_number(db, "invoice_no_seq", "INV"), student_id=st.id,
                     academic_year_id=year_id, period_label=period, issue_date=issue, due_date=due,
                     total_amount=total, discount_amount=discount, paid_amount=ZERO, status="unpaid")
    db.add(inv)
    db.flush()
    db.add_all(FeeInvoiceItem(invoice_id=inv.id, fee_head_id=hid, description=desc, amount=amt) for hid, desc, amt in items)
    if total - discount <= 0:
        inv.status = "paid"
    return inv


def _notify_invoice(db: Session, inv: FeeInvoice, student_name: str) -> None:
    notify_users(db, parent_user_ids_of_student(db, inv.student_id), f"Fee invoice {inv.invoice_no}",
                 f"{student_name}: {inv.period_label} fee of PKR {service.net_amount(inv):,.0f} is due on "
                 f"{inv.due_date.strftime('%d %b %Y')}.", "fee", "fee_invoice", inv.id)


def _dup(db: Session, student_id, period) -> bool:
    return db.scalar(select(FeeInvoice.id).where(FeeInvoice.student_id == student_id, FeeInvoice.period_label == period,
                                                 FeeInvoice.status != "cancelled")) is not None


@router.post("/fee-invoices", response_model=InvoiceOut, status_code=201)
def create_invoice(body: InvoiceCreate, user: User = admin_only, db: Session = Depends(get_db)):
    st = db.get(Student, body.student_id)
    if st is None or not st.is_active:
        raise ValidationFailed(errors=[field_error("student_id", "Active student not found")])
    issue = body.issue_date or school_today()
    if body.due_date < issue:
        raise ValidationFailed(errors=[field_error("due_date", "Due date cannot be before the issue date")])
    year_id = current_year_id(db)
    period = body.period_label.strip()
    if _dup(db, st.id, period):
        raise Conflict(f"An invoice for {period} already exists for this student", code="duplicate_invoice")
    if body.items:
        heads = {h.id: h for h in db.scalars(select(FeeHead).where(FeeHead.id.in_({i.fee_head_id for i in body.items})))}
        missing = [i for i, it in enumerate(body.items) if it.fee_head_id not in heads]
        if missing:
            raise ValidationFailed(errors=[field_error(f"items.{i}.fee_head_id", "Fee head does not exist") for i in missing])
        items = [(i.fee_head_id, i.description or heads[i.fee_head_id].name, i.amount) for i in body.items]
    else:
        found = _structure_items(db, _class_of_student(db, st), year_id, None)
        if not found:
            raise BadRequest("No monthly fee structure is defined for this student's class; provide items",
                             code="no_fee_structure")
        items = [(h.id, h.name, s.amount) for s, h in found]
    total = sum((a for _, _, a in items), ZERO)
    if body.discount_amount > total:
        raise ValidationFailed(errors=[field_error("discount_amount", "Discount cannot exceed the invoice total")])
    inv = _new_invoice(db, st, year_id, period, issue, body.due_date, items, body.discount_amount)
    _notify_invoice(db, inv, st.full_name)
    db.commit()
    return service.invoices_out(db, [inv], detail=True)[0]


@router.post("/fee-invoices/generate")
def generate_invoices(body: GenerateBody, user: User = admin_only, db: Session = Depends(get_db)):
    issue = body.issue_date or school_today()
    if body.due_date < issue:
        raise ValidationFailed(errors=[field_error("due_date", "Due date cannot be before the issue date")])
    if body.section_id:
        if db.get(Section, body.section_id) is None:
            raise NotFound("Section not found")
        stmt = select(Student).where(Student.section_id == body.section_id, Student.is_active)
    else:
        if db.get(SchoolClass, body.class_id) is None:
            raise NotFound("Class not found")
        stmt = select(Student).join(Section, Section.id == Student.section_id).where(
            Section.class_id == body.class_id, Student.is_active)
    year_id, period = current_year_id(db), body.period_label.strip()
    created, skipped_existing, skipped_no_structure, ids = 0, 0, 0, []
    struct_cache: dict[uuid.UUID, list] = {}
    for st in db.scalars(stmt.order_by(Student.roll_no)):
        if _dup(db, st.id, period):
            skipped_existing += 1
            continue
        cid = _class_of_student(db, st)
        if cid not in struct_cache:
            struct_cache[cid] = _structure_items(db, cid, year_id, body.fee_head_ids)
        found = struct_cache[cid]
        if not found:
            skipped_no_structure += 1
            continue
        inv = _new_invoice(db, st, year_id, period, issue, body.due_date, [(h.id, h.name, s.amount) for s, h in found], ZERO)
        _notify_invoice(db, inv, st.full_name)
        ids.append(inv.id)
        created += 1
    db.commit()
    return {"created": created, "skipped_existing": skipped_existing, "skipped_no_structure": skipped_no_structure,
            "invoice_ids": ids}


def _scoped_invoices(user: User, db: Session):
    stmt = select(FeeInvoice)
    if user.role == "admin":
        return stmt
    kids = parent_child_ids(user, db)
    return stmt.where(FeeInvoice.student_id.in_(kids), FeeInvoice.status != "cancelled") if kids else stmt.where(False)


@router.get("/fee-invoices", response_model=Page[InvoiceOut])
def list_invoices(student_id: uuid.UUID | None = None,
                  status: Literal["unpaid", "partial", "paid", "overdue", "cancelled"] | None = None,
                  period_label: str | None = Query(None, max_length=30), section_id: uuid.UUID | None = None,
                  class_id: uuid.UUID | None = None, due_from: date | None = None, due_to: date | None = None,
                  params: PageParams = Depends(page_params), user: User = admin_parent, db: Session = Depends(get_db)):
    stmt = _scoped_invoices(user, db)
    if student_id:
        if user.role == "parent":
            linked_child(user, db, student_id)
        stmt = stmt.where(FeeInvoice.student_id == student_id)
    if section_id or class_id:
        stmt = stmt.join(Student, Student.id == FeeInvoice.student_id)
        if section_id:
            stmt = stmt.where(Student.section_id == section_id)
        if class_id:
            stmt = stmt.join(Section, Section.id == Student.section_id).where(Section.class_id == class_id)
    if status:
        stmt = service.apply_status_filter(stmt, status)
    if period_label:
        stmt = stmt.where(FeeInvoice.period_label == period_label)
    if due_from:
        stmt = stmt.where(FeeInvoice.due_date >= due_from)
    if due_to:
        stmt = stmt.where(FeeInvoice.due_date <= due_to)
    rows, total = paginate(db, stmt.order_by(FeeInvoice.due_date.desc(), FeeInvoice.invoice_no.desc()), params)
    return Page(items=service.invoices_out(db, [r[0] for r in rows]), total=total, page=params.page, page_size=params.page_size)


def _invoice(db: Session, user: User, invoice_id: uuid.UUID) -> FeeInvoice:
    inv = db.scalar(_scoped_invoices(user, db).where(FeeInvoice.id == invoice_id))
    if inv is None:
        raise NotFound("Invoice not found")
    return inv


@router.get("/fee-invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: uuid.UUID, user: User = admin_parent, db: Session = Depends(get_db)):
    return service.invoices_out(db, [_invoice(db, user, invoice_id)], detail=True)[0]


def _locked_invoice(db: Session, invoice_id: uuid.UUID) -> FeeInvoice:
    inv = db.scalar(select(FeeInvoice).where(FeeInvoice.id == invoice_id).with_for_update())
    if inv is None:
        raise NotFound("Invoice not found")
    return inv


@router.post("/fee-invoices/{invoice_id}/payments", response_model=InvoiceOut, status_code=201)
def record_payment(invoice_id: uuid.UUID, body: PaymentCreate, user: User = admin_only, db: Session = Depends(get_db)):
    _invoice(db, user, invoice_id)
    inv = _locked_invoice(db, invoice_id)        # row lock: two cashiers cannot overpay concurrently
    if inv.status == "cancelled":
        raise BadRequest("This invoice is cancelled", code="invoice_cancelled")
    due = service.balance(inv)
    errors = []
    if body.amount > due:
        errors.append(field_error("amount", f"Amount exceeds the outstanding balance of {due}"))
    if body.payment_date > school_today():
        errors.append(field_error("payment_date", "Payment date cannot be in the future"))
    if errors:
        raise ValidationFailed(errors=errors)
    pay = FeePayment(receipt_no=service.next_number(db, "receipt_no_seq", "RCP"), invoice_id=inv.id, amount=body.amount,
                     payment_date=body.payment_date, method=body.method, reference=body.reference,
                     remarks=body.remarks, recorded_by=user.id)
    db.add(pay)
    inv.paid_amount = Decimal(inv.paid_amount) + body.amount
    service.recompute_status(inv)
    db.flush()
    st = db.get(Student, inv.student_id)
    notify_users(db, parent_user_ids_of_student(db, inv.student_id), f"Payment received — {pay.receipt_no}",
                 f"PKR {body.amount:,.0f} received for {st.full_name} ({inv.period_label}). "
                 f"Remaining balance: PKR {service.balance(inv):,.0f}.", "fee", "fee_payment", pay.id)
    db.commit()
    return service.invoices_out(db, [inv], detail=True)[0]


@router.get("/fee-payments/{payment_id}")
def get_payment(payment_id: uuid.UUID, user: User = admin_parent, db: Session = Depends(get_db)):
    p = db.get(FeePayment, payment_id)
    if p is None:
        raise NotFound("Payment not found")
    _invoice(db, user, p.invoice_id)  # 404 unless the caller may see the invoice
    return service.get_fee_receipt_data(db, payment_id)


@router.post("/fee-payments/{payment_id}/reverse", response_model=InvoiceOut, status_code=201)
def reverse_payment(payment_id: uuid.UUID, body: ReverseBody, user: User = admin_only, db: Session = Depends(get_db)):
    p = db.get(FeePayment, payment_id)
    if p is None:
        raise NotFound("Payment not found")
    inv = _locked_invoice(db, p.invoice_id)
    if p.is_reversal:
        raise BadRequest("A reversal cannot be reversed", code="already_reversal")
    if service.reversed_payment_ids(db, [p.id]):
        raise Conflict("This payment has already been reversed", code="already_reversed")
    rev = FeePayment(receipt_no=service.next_number(db, "receipt_no_seq", "REV"), invoice_id=inv.id, amount=p.amount,
                     payment_date=school_today(), method=p.method, reference=p.receipt_no, remarks=body.reason.strip(),
                     recorded_by=user.id, is_reversal=True, reversal_of_id=p.id)
    db.add(rev)
    inv.paid_amount = Decimal(inv.paid_amount) - p.amount
    service.recompute_status(inv)
    db.commit()
    return service.invoices_out(db, [inv], detail=True)[0]


@router.post("/fee-invoices/{invoice_id}/cancel", response_model=InvoiceOut)
def cancel_invoice(invoice_id: uuid.UUID, user: User = admin_only, db: Session = Depends(get_db)):
    _invoice(db, user, invoice_id)
    inv = _locked_invoice(db, invoice_id)
    if inv.status == "cancelled":
        raise Conflict("This invoice is already cancelled")
    if Decimal(inv.paid_amount) > 0:
        raise Conflict("An invoice with payments cannot be cancelled. Reverse the payments first.", code="has_payments")
    inv.status = "cancelled"
    db.commit()
    return service.invoices_out(db, [inv], detail=True)[0]


# ============================================================ summary & statements
@router.get("/fee-summary")
def fee_summary(class_id: uuid.UUID | None = None, section_id: uuid.UUID | None = None,
                period_label: str | None = Query(None, max_length=30), user: User = admin_only, db: Session = Depends(get_db)):
    where = []
    if section_id:
        where.append(Student.section_id == section_id)
    if class_id:
        where.append(Student.section_id.in_(select(Section.id).where(Section.class_id == class_id)))
    if period_label:
        where.append(FeeInvoice.period_label == period_label)
    out = service.summary(db, where)
    if not (class_id or section_id):  # per-class breakdown for the dashboard
        out["by_class"] = []
        for c in db.scalars(select(SchoolClass).where(SchoolClass.is_active).order_by(SchoolClass.grade_level)):
            sub = service.summary(db, where + [Student.section_id.in_(select(Section.id).where(Section.class_id == c.id))])
            if sub["invoices"]:
                out["by_class"].append({"class_id": c.id, "class_name": c.name, **{k: sub[k] for k in
                                        ("invoices", "billed", "collected", "outstanding", "overdue")}})
    return out


@router.get("/students/{student_id}/fee-statement")
def fee_statement(student_id: uuid.UUID, user: User = admin_parent, db: Session = Depends(get_db)):
    if db.get(Student, student_id) is None or not can_access_student(user, student_id, db):
        raise NotFound("Student not found")
    data = service.get_fee_statement_data(db, student_id)
    if user.role == "parent":  # cancelled invoices are an admin matter
        data["invoices"] = [i for i in data["invoices"] if i.status != "cancelled"]
        data["totals"] = service.statement_totals(data["invoices"])
    return data
