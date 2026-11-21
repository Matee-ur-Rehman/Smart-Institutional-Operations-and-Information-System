"""Reports: PDF/CSV generation, content spot-checks and authorization (mirrors the JSON endpoints)."""
import csv
import io
from datetime import timedelta

import pytest
from pypdf import PdfReader

from tests.conftest import entries
from tests.foundation.test_attendance import put, school_day


def text_of(resp) -> str:
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("application/pdf") and resp.content.startswith(b"%PDF")
    assert "attachment" in resp.headers["content-disposition"]
    return "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(resp.content)).pages)


def rows_of(resp):
    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/csv")
    return list(csv.reader(io.StringIO(resp.content.decode("utf-8-sig"))))


@pytest.fixture
def published(api, world, make_exam):
    w = world
    exam, papers = make_exam()
    api.put(f"/exam-schedules/{papers['math']['id']}/marks", w.ua, json=entries((w.a1, 90), (w.a2, 20), (w.a3, 70)))
    api.put(f"/exam-schedules/{papers['eng']['id']}/marks", w.ua, json=entries((w.a1, 80), (w.a2, 35), (w.a3, 75)))
    return exam


def test_result_card_content_and_access(api, world, published):
    w, eid = world, published["id"]
    url = f"/reports/result-card/{w.a1.id}?exam_id={eid}"
    assert api.get(url, w.user_a1).status_code == 404 and api.get(url, w.up1).status_code == 404   # not published yet
    t = text_of(api.get(url, w.ua))                                                                   # teachers see drafts of own class
    assert "Ali Ahmed" in t and "Mathematics" in t
    api.post(f"/exams/{eid}/publish-results", w.admin)
    t = text_of(api.get(url, w.user_a1))
    assert "RESULT CARD" in t and "Midterm 2026" in t and "PASS" in t and "A1" in t
    assert "170" in t and "200" in t                                                                  # 90 + 80 of 200
    assert api.get(url, w.up1).status_code == 200 and api.get(url, w.admin).status_code == 200
    assert api.get(url, w.user_a2).status_code == 404 and api.get(url, w.up2).status_code == 404
    assert api.get(url, w.ub).status_code == 404 and api.get(url).status_code == 401
    assert api.get(f"/reports/result-card/{w.a1.id}?exam_id={w.a1.id}", w.admin).status_code == 404  # unknown exam
    assert "FAIL" in text_of(api.get(f"/reports/result-card/{w.a2.id}?exam_id={eid}", w.admin))


def test_class_results_pdf_and_csv(api, world, published):
    w, eid = world, published["id"]
    url = f"/reports/results/sections/{w.sec_a.id}?exam_id={eid}"
    assert "CLASS RESULT SHEET" in text_of(api.get(url, w.ua))
    rows = rows_of(api.get(url + "&format=csv", w.admin))
    assert rows[0][:3] == ["Position", "Roll No", "Name"] and len(rows) == 4
    assert rows[1][1] == "A1" and rows[1][0] == "1"                                                   # topper first
    assert api.get(url, w.ub).status_code == 404 and api.get(url, w.user_a1).status_code == 403
    assert api.get(url + "&format=xml", w.admin).status_code == 422


def test_fee_receipt_and_statement(api, world):
    w = world
    h = api.post("/fee-heads", w.admin, json={"name": "Tuition Fee", "frequency": "monthly"}).json()
    api.post("/fee-structures", w.admin, json={"class_id": str(w.class8.id), "fee_head_id": h["id"], "amount": 5000})
    inv = api.post("/fee-invoices", w.admin, json={"student_id": str(w.a1.id), "period_label": "October 2026",
                                                  "due_date": str(w.today + timedelta(days=5))}).json()
    paid = api.post(f"/fee-invoices/{inv['id']}/payments", w.admin,
                    json={"amount": 2000, "payment_date": str(w.today), "method": "cash"}).json()
    pid = paid["payments"][0]["id"]
    t = text_of(api.get(f"/reports/fee-receipt/{pid}", w.up1))
    assert "FEE RECEIPT" in t and "Ali Ahmed" in t and "2,000.00" in t and "3,000.00" in t
    assert api.get(f"/reports/fee-receipt/{pid}", w.admin).status_code == 200
    assert api.get(f"/reports/fee-receipt/{pid}", w.up2).status_code == 404                           # other family
    for u in (w.user_a1, w.ua):
        assert api.get(f"/reports/fee-receipt/{pid}", u).status_code == 403
        assert api.get(f"/reports/fee-statement/{w.a1.id}", u).status_code == 403
    st = text_of(api.get(f"/reports/fee-statement/{w.a1.id}", w.up1))
    assert "FEE STATEMENT" in st and "October 2026" in st and "5,000.00" in st
    assert api.get(f"/reports/fee-statement/{w.a1.id}", w.up2).status_code == 404
    api.post(f"/fee-payments/{pid}/reverse", w.admin, json={"reason": "Entered on wrong invoice"})
    assert "REVERSED" in text_of(api.get(f"/reports/fee-receipt/{pid}", w.admin))


def test_timetable_pdf_visibility(api, world):
    w = world
    p = api.post("/period-definitions", w.admin, json={"period_no": 1, "start_time": "08:00", "end_time": "08:40", "label": "Period 1"}).json()
    api.post("/timetable-slots", w.admin, json={"section_id": str(w.sec_a.id), "subject_id": str(w.math.id), "day_of_week": 1,
                                               "period_id": p["id"], "room": "R-8A"})
    url = f"/reports/timetable/{w.sec_a.id}"
    t = text_of(api.get(url, w.user_a1))
    assert "WEEKLY TIMETABLE" in t and "Mathematics" in t and "Teacher A" in t and "R-8A" in t
    for u in (w.admin, w.ua, w.up1):                                                                  # parent's child is in 8-A
        assert api.get(url, u).status_code == 200
    assert api.get(url, w.user_b1).status_code == 404 and api.get(url, w.ub).status_code == 404
    assert api.get(url, w.up2).status_code == 404 and api.get(url).status_code == 401


def test_attendance_reports(api, world):
    w = world
    d = school_day(w.today)
    put(api, w.admin, w, w.sec_a, [(w.a1, "present"), (w.a2, "absent"), (w.a3, "late")], d)
    url = f"/reports/attendance/students/{w.a2.id}?from_date={d}&to_date={d}"
    t = text_of(api.get(url, w.ua))
    assert "ATTENDANCE REPORT" in t and "Bilal Khan" in t and "Absent" in t
    assert rows_of(api.get(url + "&format=csv", w.admin))[1][1] == "absent"
    assert api.get(url, w.user_a2).status_code == 200 and api.get(url, w.user_a1).status_code == 404
    assert api.get(f"/reports/attendance/students/{w.a1.id}", w.up2).status_code == 404
    sec = f"/reports/attendance/sections/{w.sec_a.id}?from_date={d}&to_date={d}"
    assert "CLASS ATTENDANCE REPORT" in text_of(api.get(sec, w.ua))
    rows = rows_of(api.get(sec + "&format=csv", w.admin))
    assert rows[0][0] == "Roll No" and [r[8] for r in rows[1:]] == ["", "LOW", ""]
    assert api.get(sec, w.ub).status_code == 404 and api.get(sec, w.up1).status_code == 403


def test_student_list_csv_admin_only(api, world):
    w = world
    rows = rows_of(api.get("/reports/students", w.admin))
    assert len(rows) == 7 and rows[0][0] == "Roll No"
    assert "Parent One" in [r for r in rows if r[0] == "A1"][0][6]
    assert len(rows_of(api.get(f"/reports/students?section_id={w.sec_b.id}", w.admin))) == 3
    for u in (w.ua, w.up1, w.user_a1):
        assert api.get("/reports/students", u).status_code == 403
