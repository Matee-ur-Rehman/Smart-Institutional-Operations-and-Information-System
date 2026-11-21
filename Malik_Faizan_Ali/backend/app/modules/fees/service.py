"""Fee business logic. Money is Decimal everywhere (NUMERIC(12,2) in the DB), never float."""
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import Session

from app.common.scope import section_labels, student_labels, user_names
from app.common.timeutil import school_today
from app.core.errors import NotFound
from app.modules.fees.models import FeeInvoice, FeeInvoiceItem, FeePayment
from app.modules.fees.schemas import InvoiceOut, ItemOut, PaymentOut
from app.modules.foundation.models import Student

ZERO = Decimal("0.00")
SCHOOL_NAME = "Trends High School Hassan Abdal"


def next_number(db: Session, seq: str, prefix: str, with_year: bool = True) -> str:
    n = db.scalar(text(f"SELECT nextval('{seq}')"))
    year = f"{school_today().year}-" if with_year else ""
    return f"{prefix}-{year}{n:06d}"


def net_amount(inv: FeeInvoice) -> Decimal:
    return Decimal(inv.total_amount) - Decimal(inv.discount_amount)


def balance(inv: FeeInvoice) -> Decimal:
    return net_amount(inv) - Decimal(inv.paid_amount)


def display_status(inv: FeeInvoice, today: date | None = None) -> str:
    """'overdue' is derived on read (no scheduled job): unpaid/partial and past the due date."""
    if inv.status in ("unpaid", "partial") and inv.due_date < (today or school_today()):
        return "overdue"
    return inv.status


def overdue_clause(today: date | None = None):
    return and_(FeeInvoice.status.in_(("unpaid", "partial")), FeeInvoice.due_date < (today or school_today()))


def apply_status_filter(stmt, status: str, today: date | None = None):
    today = today or school_today()
    if status == "overdue":
        return stmt.where(overdue_clause(today))
    if status in ("unpaid", "partial"):
        return stmt.where(FeeInvoice.status == status, FeeInvoice.due_date >= today)
    return stmt.where(FeeInvoice.status == status)


def recompute_status(inv: FeeInvoice) -> None:
    if inv.status == "cancelled":
        return
    paid, net = Decimal(inv.paid_amount), net_amount(inv)
    inv.status = "paid" if paid >= net else ("partial" if paid > 0 else "unpaid")


def reversed_payment_ids(db: Session, payment_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if not payment_ids:
        return set()
    return set(db.scalars(select(FeePayment.reversal_of_id).where(FeePayment.reversal_of_id.in_(payment_ids))))


def payments_out(db: Session, rows: list[FeePayment]) -> list[PaymentOut]:
    names = user_names(db, {p.recorded_by for p in rows})
    rev = reversed_payment_ids(db, [p.id for p in rows if not p.is_reversal])
    return [PaymentOut(id=p.id, receipt_no=p.receipt_no, invoice_id=p.invoice_id, amount=p.amount,
                       payment_date=p.payment_date, method=p.method, reference=p.reference, remarks=p.remarks,
                       recorded_by_name=names.get(p.recorded_by), is_reversal=p.is_reversal,
                       reversal_of_id=p.reversal_of_id, is_reversed=p.id in rev, created_at=p.created_at)
            for p in rows]


def invoices_out(db: Session, rows: list[FeeInvoice], detail: bool = False) -> list[InvoiceOut]:
    if not rows:
        return []
    studs = student_labels(db, {r.student_id for r in rows})
    today = school_today()
    items_by, pays_by = {}, {}
    if detail:
        ids = [r.id for r in rows]
        for it in db.scalars(select(FeeInvoiceItem).where(FeeInvoiceItem.invoice_id.in_(ids)).order_by(FeeInvoiceItem.description)):
            items_by.setdefault(it.invoice_id, []).append(ItemOut(id=it.id, fee_head_id=it.fee_head_id,
                                                                  description=it.description, amount=it.amount))
        pays = list(db.scalars(select(FeePayment).where(FeePayment.invoice_id.in_(ids)).order_by(FeePayment.created_at, FeePayment.id)))
        for p in payments_out(db, pays):
            pays_by.setdefault(p.invoice_id, []).append(p)
    out = []
    for r in rows:
        s = studs.get(r.student_id, {})
        out.append(InvoiceOut(
            id=r.id, invoice_no=r.invoice_no, student_id=r.student_id, student_name=s.get("full_name"),
            roll_no=s.get("roll_no"), section_label=s.get("section_label"), period_label=r.period_label,
            issue_date=r.issue_date, due_date=r.due_date, total_amount=r.total_amount, discount_amount=r.discount_amount,
            net_amount=net_amount(r), paid_amount=r.paid_amount, balance=balance(r), status=display_status(r, today),
            items=items_by.get(r.id, []) if detail else None, payments=pays_by.get(r.id, []) if detail else None,
            created_at=r.created_at))
    return out


def statement_totals(invoices: list[InvoiceOut]) -> dict:
    live = [i for i in invoices if i.status != "cancelled"]
    return {
        "billed": sum((i.net_amount for i in live), ZERO),
        "paid": sum((i.paid_amount for i in live), ZERO),
        "balance": sum((i.balance for i in live), ZERO),
        "overdue": sum((i.balance for i in live if i.status == "overdue"), ZERO),
    }


def get_fee_statement_data(db: Session, student_id: uuid.UUID) -> dict:
    """Plain-dict data for Member 1's PDF engine (API_CONTRACT.md section 5)."""
    st = db.get(Student, student_id)
    if st is None:
        raise NotFound("Student not found")
    invs = list(db.scalars(select(FeeInvoice).where(FeeInvoice.student_id == student_id)
                           .order_by(FeeInvoice.issue_date.desc(), FeeInvoice.invoice_no.desc())))
    out = invoices_out(db, invs, detail=True)
    return {"school": SCHOOL_NAME,
            "student": {"id": st.id, "roll_no": st.roll_no, "full_name": st.full_name,
                        "section_label": section_labels(db, [st.section_id]).get(st.section_id)},
            "invoices": out, "totals": statement_totals(out)}


def get_fee_receipt_data(db: Session, payment_id: uuid.UUID) -> dict:
    p = db.get(FeePayment, payment_id)
    if p is None:
        raise NotFound("Payment not found")
    inv = db.get(FeeInvoice, p.invoice_id)
    return {"school": SCHOOL_NAME, "payment": payments_out(db, [p])[0], "invoice": invoices_out(db, [inv], detail=False)[0]}


def summary(db: Session, where: list) -> dict:
    today = school_today()
    base = select(FeeInvoice).join(Student, Student.id == FeeInvoice.student_id).where(FeeInvoice.status != "cancelled", *where)
    rows = list(db.scalars(base))
    billed = sum((net_amount(r) for r in rows), ZERO)
    collected = sum((Decimal(r.paid_amount) for r in rows), ZERO)
    overdue_amt = sum((balance(r) for r in rows if display_status(r, today) == "overdue"), ZERO)
    counts: dict[str, int] = {}
    for r in rows:
        s = display_status(r, today)
        counts[s] = counts.get(s, 0) + 1
    return {"invoices": len(rows), "billed": billed, "collected": collected, "outstanding": billed - collected,
            "overdue": overdue_amt, "collection_rate": float(round(collected / billed * 100, 1)) if billed else 0.0,
            "by_status": counts}
