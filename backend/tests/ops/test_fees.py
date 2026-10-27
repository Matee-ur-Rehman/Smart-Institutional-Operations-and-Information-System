"""Module: Fee Management (admin records everything; parents see only their own children)."""
import pytest

from tests.conftest import assert_validation_error
from tests.ops.helpers import day, ids

BASE = "/api/v1"


@pytest.fixture
def fees(client, world, h):
    """Fee heads Tuition (monthly) and Admission (one-time); Class 8 pays 3000 + 5000."""
    admin = h(world.admin)
    tuition = client.post(f"{BASE}/fee-heads", json={"name": "Tuition", "frequency": "monthly"}, headers=admin).json()
    admission = client.post(f"{BASE}/fee-heads", json={"name": "Admission", "frequency": "one_time"}, headers=admin).json()
    for head, amount in ((tuition, 3000), (admission, 5000)):
        r = client.post(
            f"{BASE}/fee-structures",
            json={"class_id": str(world.class_8.id), "fee_head_id": head["id"], "amount": amount},
            headers=admin,
        )
        assert r.status_code == 201, r.text
    return {"tuition": tuition, "admission": admission}


def make_invoice(client, world, h, student=None, period="October 2026", due=7, items=None, discount=0):
    body = {"student_id": str((student or world.st_a1).id), "period_label": period, "due_date": day(due), "discount_amount": discount}
    if items is not None:
        body["items"] = items
    r = client.post(f"{BASE}/fee-invoices", json=body, headers=h(world.admin))
    assert r.status_code == 201, r.text
    return r.json()


def pay(client, world, h, invoice_id, amount, **extra):
    body = {"amount": amount, "payment_date": day(0), "method": "cash", **extra}
    return client.post(f"{BASE}/fee-invoices/{invoice_id}/payments", json=body, headers=h(world.admin))


# ---------------------------------------------------------------- setup data
def test_fee_head_and_structure_validation(client, world, h, fees):
    admin = h(world.admin)
    assert client.post(f"{BASE}/fee-heads", json={"name": "Tuition", "frequency": "monthly"}, headers=admin).status_code == 409
    assert client.post(f"{BASE}/fee-heads", json={"name": "Bus", "frequency": "weekly"}, headers=admin).status_code == 422
    dup = {"class_id": str(world.class_8.id), "fee_head_id": fees["tuition"]["id"], "amount": 100}
    assert client.post(f"{BASE}/fee-structures", json=dup, headers=admin).status_code == 409
    for bad in (0, -5, 10.123):
        r = client.post(f"{BASE}/fee-structures", json={**dup, "class_id": str(world.class_9.id), "amount": bad}, headers=admin)
        assert_validation_error(r, "amount")


def test_fee_head_in_use_cannot_be_deleted(client, world, h, fees):
    admin = h(world.admin)
    assert client.delete(f"{BASE}/fee-heads/{fees['tuition']['id']}", headers=admin).status_code == 409
    spare = client.post(f"{BASE}/fee-heads", json={"name": "Library", "frequency": "yearly"}, headers=admin).json()
    assert client.delete(f"{BASE}/fee-heads/{spare['id']}", headers=admin).status_code == 204


# ---------------------------------------------------------------- invoices
def test_invoice_from_class_fee_structure_uses_monthly_heads(client, world, h, notes, fees):
    inv = make_invoice(client, world, h)
    assert inv["total_amount"] == 3000 and inv["net_amount"] == 3000 and inv["balance"] == 3000
    assert inv["status"] == "unpaid" and inv["invoice_no"].startswith("INV-")
    assert [i["description"] for i in inv["items"]] == ["Tuition"]
    assert len(notes(world.pu_a, "fee")) == 1  # the parent of A1 is told
    assert notes(world.pu_b, "fee") == []


def test_invoice_with_explicit_items_and_discount(client, world, h, fees):
    inv = make_invoice(
        client, world, h, period="Annual 2026",
        items=[{"description": "Annual charges", "amount": 2500}, {"description": "Sports fee", "amount": 500.50}],
        discount=500,
    )
    assert inv["total_amount"] == 3000.5 and inv["net_amount"] == 2500.5


def test_discount_cannot_exceed_total(client, world, h, fees):
    body = {"student_id": str(world.st_a1.id), "period_label": "October 2026", "due_date": day(7), "discount_amount": 99999}
    assert client.post(f"{BASE}/fee-invoices", json=body, headers=h(world.admin)).status_code == 400


def test_one_invoice_per_student_per_period(client, world, h, fees):
    make_invoice(client, world, h)
    body = {"student_id": str(world.st_a1.id), "period_label": "October 2026", "due_date": day(7)}
    assert client.post(f"{BASE}/fee-invoices", json=body, headers=h(world.admin)).status_code == 409


def test_class_without_fee_structure_needs_explicit_items(client, world, h, fees, db):
    from app.modules.ops_common.core_refs import Student

    st = Student(roll_no="N-01", full_name="Nine A", section_id=world.section_9a.id)
    db.add(st)
    db.commit()
    body = {"student_id": str(st.id), "period_label": "October 2026", "due_date": day(7)}
    assert client.post(f"{BASE}/fee-invoices", json=body, headers=h(world.admin)).status_code == 400


def test_generate_invoices_for_a_section_is_idempotent(client, world, h, fees):
    body = {"section_id": str(world.section_a.id), "period_label": "November 2026", "due_date": day(10)}
    first = client.post(f"{BASE}/fee-invoices/generate", json=body, headers=h(world.admin))
    assert first.status_code == 200
    assert first.json() == {"created": 2, "skipped_existing": 0, "skipped_no_fee_structure": 0}
    again = client.post(f"{BASE}/fee-invoices/generate", json=body, headers=h(world.admin)).json()
    assert again == {"created": 0, "skipped_existing": 2, "skipped_no_fee_structure": 0}


def test_generate_for_whole_class_skips_existing(client, world, h, fees):
    section = {"section_id": str(world.section_a.id), "period_label": "November 2026", "due_date": day(10)}
    client.post(f"{BASE}/fee-invoices/generate", json=section, headers=h(world.admin))
    whole = {"class_id": str(world.class_8.id), "period_label": "November 2026", "due_date": day(10)}
    result = client.post(f"{BASE}/fee-invoices/generate", json=whole, headers=h(world.admin)).json()
    assert result["created"] == 1 and result["skipped_existing"] == 2  # only B1 is new


def test_generate_needs_exactly_one_target(client, world, h, fees):
    both = {"class_id": str(world.class_8.id), "section_id": str(world.section_a.id), "period_label": "November 2026", "due_date": day(10)}
    neither = {"period_label": "November 2026", "due_date": day(10)}
    assert_validation_error(client.post(f"{BASE}/fee-invoices/generate", json=both, headers=h(world.admin)))
    assert_validation_error(client.post(f"{BASE}/fee-invoices/generate", json=neither, headers=h(world.admin)))


def test_class_with_no_students_or_structure_creates_nothing(client, world, h, fees):
    body = {"section_id": str(world.section_9a.id), "period_label": "November 2026", "due_date": day(10)}
    assert client.post(f"{BASE}/fee-invoices/generate", json=body, headers=h(world.admin)).json()["created"] == 0


# ---------------------------------------------------------------- payments
def test_partial_then_full_payment(client, world, h, notes, fees):
    inv = make_invoice(client, world, h)
    first = pay(client, world, h, inv["id"], 1000, reference="Slip 17")
    assert first.status_code == 201
    assert first.json()["receipt_no"].startswith("RCT-") and first.json()["amount"] == 1000
    mid = client.get(f"{BASE}/fee-invoices/{inv['id']}", headers=h(world.admin)).json()
    assert mid["status"] == "partial" and mid["paid_amount"] == 1000 and mid["balance"] == 2000
    assert pay(client, world, h, inv["id"], 2000).status_code == 201
    done = client.get(f"{BASE}/fee-invoices/{inv['id']}", headers=h(world.admin)).json()
    assert done["status"] == "paid" and done["balance"] == 0 and len(done["payments"]) == 2
    assert len(notes(world.pu_a, "fee")) == 3  # invoice + two payments


def test_overpayment_and_bad_amounts_are_rejected(client, world, h, fees):
    inv = make_invoice(client, world, h)
    assert pay(client, world, h, inv["id"], 3000.01).status_code == 400
    for bad in (0, -10, 1.234):
        assert_validation_error(pay(client, world, h, inv["id"], bad), "amount")
    assert_validation_error(pay(client, world, h, inv["id"], 100, method="bitcoin"), "method")
    future = {"amount": 100, "payment_date": day(2), "method": "cash"}
    r = client.post(f"{BASE}/fee-invoices/{inv['id']}/payments", json=future, headers=h(world.admin))
    assert_validation_error(r, "payment_date")
    after = client.get(f"{BASE}/fee-invoices/{inv['id']}", headers=h(world.admin)).json()
    assert after["paid_amount"] == 0 and after["payments"] == []


def test_paid_invoice_accepts_no_more_money(client, world, h, fees):
    inv = make_invoice(client, world, h)
    pay(client, world, h, inv["id"], 3000)
    assert pay(client, world, h, inv["id"], 1).status_code == 400


def test_only_admin_records_payments(client, world, h, fees):
    inv = make_invoice(client, world, h)
    body = {"amount": 100, "payment_date": day(0), "method": "cash"}
    for who in (world.pu_a, world.tu_a, world.su_a1):
        assert client.post(f"{BASE}/fee-invoices/{inv['id']}/payments", json=body, headers=h(who)).status_code == 403


def test_reversal_restores_the_balance_and_is_recorded(client, world, h, fees):
    inv = make_invoice(client, world, h)
    payment = pay(client, world, h, inv["id"], 3000).json()
    assert client.get(f"{BASE}/fee-invoices/{inv['id']}", headers=h(world.admin)).json()["status"] == "paid"
    short = client.post(f"{BASE}/fee-payments/{payment['id']}/reverse", json={"reason": "no"}, headers=h(world.admin))
    assert_validation_error(short, "reason")
    rev = client.post(f"{BASE}/fee-payments/{payment['id']}/reverse", json={"reason": "Entered twice by mistake"}, headers=h(world.admin))
    assert rev.status_code == 201 and rev.json()["is_reversal"] is True
    assert rev.json()["reverses_payment_id"] == payment["id"] and rev.json()["receipt_no"].startswith("REV-")
    after = client.get(f"{BASE}/fee-invoices/{inv['id']}", headers=h(world.admin)).json()
    assert after["status"] == "unpaid" and after["paid_amount"] == 0 and len(after["payments"]) == 2  # nothing deleted


def test_a_payment_is_reversed_only_once_and_reversals_are_final(client, world, h, fees):
    inv = make_invoice(client, world, h)
    payment = pay(client, world, h, inv["id"], 1000).json()
    reason = {"reason": "Entered twice by mistake"}
    rev = client.post(f"{BASE}/fee-payments/{payment['id']}/reverse", json=reason, headers=h(world.admin)).json()
    assert client.post(f"{BASE}/fee-payments/{payment['id']}/reverse", json=reason, headers=h(world.admin)).status_code == 409
    assert client.post(f"{BASE}/fee-payments/{rev['id']}/reverse", json=reason, headers=h(world.admin)).status_code == 409


def test_cancel_rules(client, world, h, fees):
    paid = make_invoice(client, world, h)
    pay(client, world, h, paid["id"], 500)
    assert client.post(f"{BASE}/fee-invoices/{paid['id']}/cancel", headers=h(world.admin)).status_code == 409
    other = make_invoice(client, world, h, period="December 2026")
    r = client.post(f"{BASE}/fee-invoices/{other['id']}/cancel", headers=h(world.admin))
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert pay(client, world, h, other["id"], 100).status_code == 409


# ---------------------------------------------------------------- overdue, filters, summary
def test_overdue_is_derived_from_the_due_date(client, world, h, fees):
    late = make_invoice(client, world, h, period="September 2026", due=-5)
    make_invoice(client, world, h, period="October 2026", due=10)
    assert client.get(f"{BASE}/fee-invoices/{late['id']}", headers=h(world.admin)).json()["status"] == "overdue"
    overdue = client.get(f"{BASE}/fee-invoices", params={"status": "overdue"}, headers=h(world.admin)).json()
    assert ids(overdue["items"]) == {late["id"]}
    unpaid = client.get(f"{BASE}/fee-invoices", params={"status": "unpaid"}, headers=h(world.admin)).json()
    assert late["id"] not in ids(unpaid["items"]) and unpaid["total"] == 1
    pay(client, world, h, late["id"], 3000)
    assert client.get(f"{BASE}/fee-invoices", params={"status": "overdue"}, headers=h(world.admin)).json()["total"] == 0


def test_invoice_filters(client, world, h, fees):
    make_invoice(client, world, h, period="October 2026")
    make_invoice(client, world, h, student=world.st_b1, period="October 2026")
    make_invoice(client, world, h, period="November 2026")
    admin = h(world.admin)
    assert client.get(f"{BASE}/fee-invoices", headers=admin).json()["total"] == 3
    assert client.get(f"{BASE}/fee-invoices", params={"period_label": "October 2026"}, headers=admin).json()["total"] == 2
    assert client.get(f"{BASE}/fee-invoices", params={"section_id": str(world.section_b.id)}, headers=admin).json()["total"] == 1
    assert client.get(f"{BASE}/fee-invoices", params={"student_id": str(world.st_a1.id)}, headers=admin).json()["total"] == 2
    assert client.get(f"{BASE}/fee-invoices", params={"status": "bogus"}, headers=admin).status_code == 422


def test_fee_summary(client, world, h, fees):
    paid = make_invoice(client, world, h)
    make_invoice(client, world, h, student=world.st_a2, due=-2)  # overdue, nothing paid
    pay(client, world, h, paid["id"], 1000)
    s = client.get(f"{BASE}/fee-summary", headers=h(world.admin)).json()
    assert s == {"billed": 6000, "collected": 1000, "outstanding": 5000, "overdue": 3000, "invoice_count": 2}


# ---------------------------------------------------------------- privacy: parents see only their children
def test_parent_sees_only_their_childs_invoices(client, world, h, fees):
    a1 = make_invoice(client, world, h)
    b1 = make_invoice(client, world, h, student=world.st_b1)
    mine = client.get(f"{BASE}/fee-invoices", headers=h(world.pu_a)).json()
    assert ids(mine["items"]) == {a1["id"]}
    assert ids(client.get(f"{BASE}/fee-invoices", headers=h(world.pu_b)).json()["items"]) == {b1["id"]}


def test_parent_cannot_open_another_childs_invoice_or_statement(client, world, h, fees):
    a1 = make_invoice(client, world, h)
    assert client.get(f"{BASE}/fee-invoices/{a1['id']}", headers=h(world.pu_a)).status_code == 200
    assert client.get(f"{BASE}/fee-invoices/{a1['id']}", headers=h(world.pu_b)).status_code == 404
    other = client.get(f"{BASE}/fee-invoices", params={"student_id": str(world.st_a1.id)}, headers=h(world.pu_b))
    assert other.status_code == 404
    url = f"{BASE}/students/{world.st_a1.id}/fee-statement"
    assert client.get(url, headers=h(world.pu_a)).status_code == 200
    assert client.get(url, headers=h(world.pu_b)).status_code == 404


@pytest.mark.parametrize("who", ["su_a1", "tu_a"])
def test_students_and_teachers_never_see_fees(client, world, h, fees, who):
    inv = make_invoice(client, world, h)
    headers = h(getattr(world, who))
    assert client.get(f"{BASE}/fee-invoices", headers=headers).status_code == 403
    assert client.get(f"{BASE}/fee-invoices/{inv['id']}", headers=headers).status_code == 403
    assert client.get(f"{BASE}/students/{world.st_a1.id}/fee-statement", headers=headers).status_code == 403


def test_fee_statement_totals(client, world, h, fees):
    one = make_invoice(client, world, h, period="October 2026")
    make_invoice(client, world, h, period="November 2026")
    pay(client, world, h, one["id"], 1200)
    data = client.get(f"{BASE}/students/{world.st_a1.id}/fee-statement", headers=h(world.admin)).json()
    assert data["student"]["roll_no"] == "A-01"
    assert data["totals"] == {"billed": 6000, "paid": 1200, "outstanding": 4800}
    assert len(data["invoices"]) == 2


def test_money_is_serialised_as_json_numbers(client, world, h, fees):
    inv = make_invoice(client, world, h)
    assert isinstance(inv["total_amount"], (int, float)) and not isinstance(inv["total_amount"], str)


def test_data_functions_for_pdf_code(db, client, world, h, fees):
    """Member 1's PDF code calls these directly (docs/API_CONTRACT.md section 5)."""
    from app.modules.fees.service import get_fee_receipt_data, get_fee_statement_data

    inv = make_invoice(client, world, h)
    payment = pay(client, world, h, inv["id"], 500).json()
    import uuid

    receipt = get_fee_receipt_data(db, uuid.UUID(payment["id"]))
    assert receipt["receipt"]["receipt_no"] == payment["receipt_no"]
    statement = get_fee_statement_data(db, world.st_a1.id)
    assert statement["student"]["name"] == "Ali Raza"
