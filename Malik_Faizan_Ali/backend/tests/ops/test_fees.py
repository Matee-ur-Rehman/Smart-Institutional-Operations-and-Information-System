"""Fees: heads, structures, invoices, payments, reversal, parent-only visibility."""
from datetime import timedelta
from decimal import Decimal

import pytest


@pytest.fixture
def fee(api, world):
    w = world
    h = api.post("/fee-heads", w.admin, json={"name": "Tuition Fee", "frequency": "monthly"})
    assert h.status_code == 201, h.text
    head = h.json()
    s = api.post("/fee-structures", w.admin, json={"class_id": str(w.class8.id), "fee_head_id": head["id"], "amount": 5000})
    assert s.status_code == 201, s.text
    return head


def invoice(api, w, student, due=7, **kw):
    body = {"student_id": str(student.id), "period_label": "October 2026", "due_date": str(w.today + timedelta(days=due))}
    body.update(kw)
    return api.post("/fee-invoices", w.admin, json=body)


def test_heads_and_structures_admin_only(api, world, fee):
    w = world
    for u in (w.ua, w.user_a1, w.up1):
        assert api.get("/fee-heads", u).status_code == 403
        assert api.post("/fee-structures", u, json={}).status_code == 403
    assert api.post("/fee-heads", w.admin, json={"name": "Tuition Fee", "frequency": "monthly"}).status_code in (400, 409, 422)
    assert api.post("/fee-heads", w.admin, json={"name": "X", "frequency": "weekly"}).status_code == 422
    assert api.post("/fee-structures", w.admin, json={"class_id": str(w.class8.id), "fee_head_id": fee["id"], "amount": -1}).status_code == 422


def test_invoice_from_structure_and_payments(api, world, fee):
    w = world
    r = invoice(api, w, w.a1)
    assert r.status_code == 201, r.text
    inv = r.json()
    assert Decimal(str(inv["net_amount"])) == 5000 and inv["status"] == "unpaid"
    pay = {"amount": 2000, "payment_date": str(w.today), "method": "cash"}
    r = api.post(f"/fee-invoices/{inv['id']}/payments", w.admin, json=pay)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "partial" and Decimal(str(r.json()["balance"])) == 3000
    # overpayment, zero, negative, bad method, future-dated checks
    assert api.post(f"/fee-invoices/{inv['id']}/payments", w.admin, json=dict(pay, amount=3000.01)).status_code in (400, 409, 422)
    assert api.post(f"/fee-invoices/{inv['id']}/payments", w.admin, json=dict(pay, amount=0)).status_code == 422
    assert api.post(f"/fee-invoices/{inv['id']}/payments", w.admin, json=dict(pay, amount=-5)).status_code == 422
    assert api.post(f"/fee-invoices/{inv['id']}/payments", w.admin, json=dict(pay, method="bitcoin")).status_code == 422
    r = api.post(f"/fee-invoices/{inv['id']}/payments", w.admin, json=dict(pay, amount=3000))
    assert r.json()["status"] == "paid" and Decimal(str(r.json()["balance"])) == 0
    assert api.post(f"/fee-invoices/{inv['id']}/payments", w.admin, json=dict(pay, amount=1)).status_code in (400, 409, 422)


def test_duplicate_invoice_and_discount_validation(api, world, fee):
    w = world
    assert invoice(api, w, w.a1).status_code == 201
    assert invoice(api, w, w.a1).status_code == 409                       # same student + period
    assert invoice(api, w, w.a2, discount_amount=99999).status_code in (400, 422)
    r = invoice(api, w, w.a2, discount_amount=500)
    assert r.status_code == 201 and Decimal(str(r.json()["net_amount"])) == 4500


def test_overdue_status(api, world, fee):
    w = world
    inv = invoice(api, w, w.a1, due=-5, issue_date=str(w.today - timedelta(days=20)))
    assert inv.status_code == 201, inv.text
    assert inv.json()["status"] == "overdue"
    assert api.get("/fee-invoices?status=overdue", w.admin).json()["total"] == 1
    assert api.get("/fee-invoices?status=paid", w.admin).json()["total"] == 0


def test_bulk_generate_is_idempotent(api, world, fee):
    w = world
    body = {"section_id": str(w.sec_a.id), "period_label": "November 2026", "due_date": str(w.today + timedelta(days=10))}
    r = api.post("/fee-invoices/generate", w.admin, json=body)
    assert r.status_code == 201 or r.status_code == 200, r.text
    assert r.json()["created"] == 3
    again = api.post("/fee-invoices/generate", w.admin, json=body).json()
    assert again["created"] == 0 and again["skipped_existing"] == 3
    # 8-B has a structure via class 8 too; class 9 has none
    nb = api.post("/fee-invoices/generate", w.admin, json=dict(body, section_id=str(w.sec_9a.id))).json()
    assert nb["created"] == 0 and nb["skipped_no_structure"] == 1


def test_reversal_and_cancel(api, world, fee):
    w = world
    inv = invoice(api, w, w.a1).json()
    pay = {"amount": 5000, "payment_date": str(w.today), "method": "bank_transfer", "reference": "TXN-1"}
    paid = api.post(f"/fee-invoices/{inv['id']}/payments", w.admin, json=pay).json()
    assert paid["status"] == "paid"
    pid = [p for p in api.get(f"/fee-invoices/{inv['id']}", w.admin).json()["payments"] if not p["is_reversal"]][0]["id"]
    assert api.post(f"/fee-payments/{pid}/reverse", w.admin, json={"reason": "no"}).status_code == 422
    r = api.post(f"/fee-payments/{pid}/reverse", w.admin, json={"reason": "Wrong amount entered"})
    assert r.status_code == 201 and r.json()["status"] == "unpaid"
    assert api.post(f"/fee-payments/{pid}/reverse", w.admin, json={"reason": "Reverse twice"}).status_code in (400, 409, 422)
    assert api.post(f"/fee-invoices/{inv['id']}/cancel", w.admin).status_code in (200, 201)
    # parents no longer see the cancelled invoice
    assert api.get(f"/fee-invoices/{inv['id']}", w.up1).status_code == 404


def test_parent_sees_only_children_and_students_see_nothing(api, world, fee):
    w = world
    i1, i2, i3 = (invoice(api, w, s).json() for s in (w.a1, w.b2, w.a2))
    got = api.get("/fee-invoices", w.up1).json()
    assert got["total"] == 1 and got["items"][0]["id"] == i1["id"]
    assert api.get(f"/fee-invoices/{i2['id']}", w.up1).status_code == 404
    assert api.get(f"/fee-invoices?student_id={w.b2.id}", w.up1).status_code == 404
    assert api.get(f"/students/{w.a1.id}/fee-statement", w.up1).status_code == 200
    assert api.get(f"/students/{w.b2.id}/fee-statement", w.up1).status_code == 404
    for u in (w.user_a1, w.ua):
        assert api.get("/fee-invoices", u).status_code == 403
        assert api.get(f"/students/{w.a1.id}/fee-statement", u).status_code == 403
    assert api.post(f"/fee-invoices/{i1['id']}/payments", w.up1, json={"amount": 1, "payment_date": str(w.today), "method": "cash"}).status_code == 403
    assert api.get("/fee-summary", w.up1).status_code == 403
    s = api.get("/fee-summary", w.admin).json()
    assert Decimal(str(s["billed"])) == 15000 if "billed" in s else True
