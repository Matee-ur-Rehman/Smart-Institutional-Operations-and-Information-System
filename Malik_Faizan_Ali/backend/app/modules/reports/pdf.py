"""PDF + CSV rendering for the reports module (reportlab). Pure functions: data in, bytes out; no DB access."""
import csv
import io
from datetime import date, datetime
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

SCHOOL = "Trends High School, Hassan Abdal"
TAGLINE = "Smart Institutional Operations and Information System"
NAVY = colors.HexColor("#1F3A5F")
LIGHT = colors.HexColor("#EEF2F7")
GRID = colors.HexColor("#B8C2CF")
GREEN, RED, AMBER = colors.HexColor("#1E7B45"), colors.HexColor("#B3261E"), colors.HexColor("#B26A00")

_ss = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=_ss["Title"], fontSize=16, textColor=NAVY, spaceAfter=2, alignment=TA_CENTER)
H2 = ParagraphStyle("h2", parent=_ss["Heading2"], fontSize=12, textColor=NAVY, spaceBefore=8, spaceAfter=4)
BODY = ParagraphStyle("body", parent=_ss["BodyText"], fontSize=9, leading=12)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=7.5, leading=9)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8, leading=10)
CENTER = ParagraphStyle("center", parent=BODY, alignment=TA_CENTER)
RIGHT = ParagraphStyle("right", parent=BODY, alignment=TA_RIGHT)


def money(v) -> str:
    return f"PKR {Decimal(str(v)):,.2f}"


def num(v) -> str:
    return "-" if v is None else f"{Decimal(str(v)):.2f}".rstrip("0").rstrip(".")


def fdate(d) -> str:
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return d.strftime("%d %b %Y") if d else "-"


def esc(s) -> str:
    return ("" if s is None else str(s)).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _page(canvas, doc):
    w, h = doc.pagesize
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, h - 22 * mm, w, 22 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 15)
    canvas.drawString(15 * mm, h - 11 * mm, SCHOOL)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(15 * mm, h - 17 * mm, TAGLINE)
    canvas.setFillColor(colors.grey)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawString(15 * mm, 9 * mm, f"Generated {datetime.now():%d %b %Y %H:%M} - computer generated document")
    canvas.drawRightString(w - 15 * mm, 9 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build(story: list, title: str, *, wide: bool = False) -> bytes:
    buf = io.BytesIO()
    size = landscape(A4) if wide else A4
    doc = SimpleDocTemplate(buf, pagesize=size, title=title, author=SCHOOL, leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=28 * mm, bottomMargin=16 * mm)
    doc.build(story, onFirstPage=_page, onLaterPages=_page)
    return buf.getvalue()


def _table(rows, widths, *, header=True, extra=None, align_right_from=None) -> Table:
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [("FONTSIZE", (0, 0), (-1, -1), 8), ("GRID", (0, 0), (-1, -1), 0.4, GRID),
             ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                  ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT])]
    if align_right_from is not None:
        style.append(("ALIGN", (align_right_from, 0), (-1, -1), "RIGHT"))
    t.setStyle(TableStyle(style + (extra or [])))
    return t


def _info(pairs: list[tuple[str, str]], cols: int = 2) -> Table:
    rows, row = [], []
    for k, v in pairs:
        row += [Paragraph(f"<b>{esc(k)}</b>", CELL), Paragraph(esc(v), CELL)]
        if len(row) == cols * 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row + [""] * (cols * 2 - len(row)))
    avail = 180 * mm
    t = Table(rows, colWidths=[avail * 0.16, avail * 0.34] * cols)
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, GRID), ("BACKGROUND", (0, 0), (0, -1), LIGHT),
                           ("BACKGROUND", (2, 0), (2, -1), LIGHT), ("TOPPADDING", (0, 0), (-1, -1), 3),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


def _signatures(*labels: str) -> Table:
    t = Table([[""] * len(labels), list(labels)], colWidths=[180 * mm / len(labels)] * len(labels), rowHeights=[16 * mm, 5 * mm])
    t.setStyle(TableStyle([("LINEABOVE", (0, 1), (-1, 1), 0.5, colors.black), ("FONTSIZE", (0, 1), (-1, 1), 8),
                           ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("TOPPADDING", (0, 1), (-1, 1), 4)]))
    return t


# ============================================================ result card
def result_card(d: dict) -> bytes:
    exam, st = d["exam"], d["student"]
    story = [Paragraph("RESULT CARD", H1), Paragraph(esc(exam["name"]), CENTER), Spacer(1, 6),
             _info([("Student", st["full_name"]), ("Roll No", st["roll_no"]), ("Class / Section", st.get("section_label") or "-"),
                    ("Exam", exam["name"]), ("Exam period", f"{fdate(exam['start_date'])} - {fdate(exam['end_date'])}"),
                    ("Position", f"{d['position']} of {d['section_size']}" if d.get("position") else "-")]), Spacer(1, 8)]
    rows = [["Subject", "Exam date", "Total", "Passing", "Obtained", "%", "Grade", "Status"]]
    extra = []
    for i, s in enumerate(d.get("subjects", []), start=1):
        obtained = num(s["marks_obtained"]) if s.get("marks_obtained") is not None else ("Absent" if s.get("state") == "absent" else "Pending")
        passed = s.get("passed")
        rows.append([s["subject_name"], fdate(s["exam_date"]), num(s["total_marks"]), num(s["passing_marks"]), obtained,
                     num(s.get("percentage")), s.get("grade") or "-", "Pass" if passed else ("Fail" if passed is False else "-")])
        if passed is not None:
            extra.append(("TEXTCOLOR", (7, i), (7, i), GREEN if passed else RED))
    story.append(_table(rows, [48 * mm, 24 * mm, 18 * mm, 18 * mm, 22 * mm, 16 * mm, 16 * mm, 18 * mm], extra=extra))
    story.append(Spacer(1, 8))
    verdict = (d.get("result") or "incomplete").upper()
    vcolor = GREEN if verdict == "PASS" else (RED if verdict == "FAIL" else AMBER)
    summary = Table([[Paragraph("<b>Total marks</b>", CELL), Paragraph(f"{num(d.get('total_obtained'))} / {num(d.get('total_marks'))}", CELL),
                      Paragraph("<b>Percentage</b>", CELL), Paragraph(f"{num(d.get('percentage'))}%", CELL),
                      Paragraph("<b>Grade</b>", CELL), Paragraph(esc(d.get("grade") or "-"), CELL),
                      Paragraph("<b>Result</b>", CELL), Paragraph(f"<b><font color='{vcolor.hexval().replace('0x', '#')}'>{verdict}</font></b>", CELL)]], colWidths=[26 * mm, 28 * mm, 24 * mm, 22 * mm, 16 * mm, 14 * mm, 18 * mm, 32 * mm])
    summary.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, NAVY), ("BACKGROUND", (0, 0), (-1, -1), LIGHT), ("FONTSIZE", (0, 0), (-1, -1), 9),
                                 ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story.append(summary)
    if not d.get("is_complete"):
        story.append(Paragraph("Note: some papers have no marks yet, so the overall result is incomplete.", SMALL))
    story += [Spacer(1, 10), _signatures("Class Teacher", "Examination Controller", "Principal")]
    return build(story, f"Result card - {st['full_name']}")


def class_results(section_label: str, exam_name: str, rows: list[dict], subjects: list[str], summary: dict) -> bytes:
    story = [Paragraph("CLASS RESULT SHEET", H1), Paragraph(f"{esc(exam_name)} - {esc(section_label)}", CENTER), Spacer(1, 6),
             _info([("Students", str(summary["students"])), ("Passed", str(summary["passed"])), ("Failed", str(summary["failed"])),
                    ("Average %", num(summary["average_percentage"]))], cols=2), Spacer(1, 8)]
    head = ["Pos", "Roll", "Name", *subjects, "Total", "%", "Grade", "Result"]
    table = [head]
    extra = []
    for i, r in enumerate(rows, start=1):
        by_sub = {s["subject_name"]: s for s in r["subjects"]}
        table.append([r.get("position") or "-", r["roll_no"], Paragraph(esc(r["full_name"]), CELL),
                      *[(num(by_sub[s]["marks_obtained"]) if s in by_sub and by_sub[s].get("marks_obtained") is not None else
                         ("Abs" if s in by_sub and by_sub[s].get("state") == "absent" else "-")) for s in subjects],
                      num(r.get("total_obtained")), num(r.get("percentage")), r.get("grade") or "-", (r.get("result") or "-").title()])
        if r.get("result") == "fail":
            extra.append(("TEXTCOLOR", (len(head) - 1, i), (len(head) - 1, i), RED))
    avail = 267 * mm
    fixed = [10 * mm, 24 * mm, 46 * mm, 16 * mm, 14 * mm, 12 * mm, 18 * mm]
    per = max(12 * mm, (avail - sum(fixed)) / max(len(subjects), 1))
    story.append(_table(table, [*fixed[:3], *[per] * len(subjects), *fixed[3:]], extra=extra))
    return build(story, f"Class results - {section_label}", wide=True)


# ============================================================ fees
def fee_receipt(d: dict) -> bytes:
    p, inv = d["payment"], d["invoice"]
    reversed_ = p.is_reversed or p.is_reversal
    story = [Paragraph("FEE RECEIPT", H1), Paragraph(f"Receipt No: <b>{esc(p.receipt_no)}</b>", CENTER), Spacer(1, 8)]
    if reversed_:
        story += [Paragraph("<font color='#B3261E'><b>THIS PAYMENT HAS BEEN REVERSED - NOT VALID AS PROOF OF PAYMENT</b></font>", CENTER), Spacer(1, 6)]
    story += [_info([("Student", inv.student_name or "-"), ("Roll No", inv.roll_no or "-"), ("Class / Section", inv.section_label or "-"),
                     ("Invoice", inv.invoice_no), ("Fee period", inv.period_label), ("Payment date", fdate(p.payment_date)),
                     ("Method", p.method.replace("_", " ").title()), ("Reference", p.reference or "-"),
                     ("Received by", p.recorded_by_name or "-"), ("Remarks", p.remarks or "-")]), Spacer(1, 8)]
    items = [["Fee head / description", "Amount"]] + [[i.description, money(i.amount)] for i in (inv.items or [])]
    if len(items) > 1:
        story.append(_table(items, [130 * mm, 50 * mm], align_right_from=1))
        story.append(Spacer(1, 6))
    sm = [["Invoice total", money(inv.total_amount)], ["Discount", money(inv.discount_amount)], ["Net payable", money(inv.net_amount)],
          ["Amount of this receipt", money(p.amount)], ["Total paid on invoice", money(inv.paid_amount)], ["Balance due", money(inv.balance)]]
    t = Table(sm, colWidths=[130 * mm, 50 * mm])
    t.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT"), ("FONTSIZE", (0, 0), (-1, -1), 9), ("GRID", (0, 0), (-1, -1), 0.4, GRID),
                           ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"), ("BACKGROUND", (0, 3), (-1, 3), LIGHT)]))
    story += [t, Spacer(1, 12), _signatures("Parent / Guardian", "Accounts Office")]
    return build(story, f"Fee receipt {p.receipt_no}")


def fee_statement(d: dict) -> bytes:
    st, t = d["student"], d["totals"]
    story = [Paragraph("FEE STATEMENT", H1), Spacer(1, 6),
             _info([("Student", st["full_name"]), ("Roll No", st["roll_no"]), ("Class / Section", st.get("section_label") or "-"),
                    ("Statement date", fdate(date.today()))]), Spacer(1, 8)]
    rows = [["Invoice", "Period", "Due date", "Net", "Paid", "Balance", "Status"]]
    extra = []
    for i, inv in enumerate(d["invoices"], start=1):
        rows.append([inv.invoice_no, inv.period_label, fdate(inv.due_date), money(inv.net_amount), money(inv.paid_amount),
                     money(inv.balance), inv.status.title()])
        col = {"paid": GREEN, "overdue": RED, "partial": AMBER}.get(inv.status)
        if col:
            extra.append(("TEXTCOLOR", (6, i), (6, i), col))
    if len(rows) == 1:
        story.append(Paragraph("No invoices have been issued yet.", BODY))
    else:
        story.append(_table(rows, [32 * mm, 30 * mm, 24 * mm, 26 * mm, 26 * mm, 26 * mm, 16 * mm], extra=extra))
    story += [Spacer(1, 8), _info([("Total billed", money(t["billed"])), ("Total paid", money(t["paid"])),
                                   ("Balance due", money(t["balance"])), ("Overdue", money(t["overdue"]))])]
    return build(story, f"Fee statement - {st['full_name']}")


# ============================================================ timetable
def timetable(d: dict) -> bytes:
    days, periods = d["days"], d["periods"]
    grid: dict[tuple[int, int], list] = {}
    for s in d["slots"]:
        grid.setdefault((s.day_of_week, s.period_no), []).append(s)
    head = ["Period", *[x["name"] for x in days]]
    rows = [head]
    extra = []
    for i, p in enumerate(periods, start=1):
        label = f"{p.label}<br/>{p.start_time:%H:%M}-{p.end_time:%H:%M}"
        row = [Paragraph(label, CELL)]
        for x in days:
            if p.is_break:
                row.append(Paragraph("<i>Break</i>", CENTER))
                continue
            cell = grid.get((x["day"], p.period_no), [])
            row.append(Paragraph("<br/>".join(f"<b>{esc(c.subject_name)}</b><br/>{esc(c.teacher_name)}" + (f"<br/>{esc(c.room)}" if c.room else "")
                                              for c in cell) or "-", CELL))
        rows.append(row)
        if p.is_break:
            extra.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FFF4D6")))
    story = [Paragraph("WEEKLY TIMETABLE", H1), Paragraph(esc(d.get("section_label") or d.get("teacher_name") or ""), CENTER), Spacer(1, 8),
             _table(rows, [24 * mm] + [(267 * mm - 24 * mm) / len(days)] * len(days), extra=extra)]
    return build(story, "Timetable", wide=True)


# ============================================================ attendance
STATUS_COLORS = {"present": GREEN, "absent": RED, "late": AMBER, "leave": colors.HexColor("#2F5DA8")}


def student_attendance(d: dict) -> bytes:
    s = d["summary"]
    story = [Paragraph("ATTENDANCE REPORT", H1), Spacer(1, 6),
             _info([("Student", d["student_name"]), ("Roll No", d["roll_no"]), ("Class / Section", d.get("section_label") or "-"),
                    ("Period", f"{fdate(d['from_date'])} - {fdate(d['to_date'])}")]), Spacer(1, 8),
             _table([["Days marked", "Present", "Late", "Absent", "Leave", "Attendance %"],
                     [s["total_days"], s["present"], s["late"], s["absent"], s["leave"],
                      f"{s['percentage']}%" if s.get("percentage") is not None else "-"]], [30 * mm] * 5 + [30 * mm]),
             Paragraph("Attendance % = (present + late) / (present + late + absent). Approved-leave days are not counted against the student.", SMALL),
             Spacer(1, 8)]
    rows, extra = [["Date", "Day", "Status", "Remarks"]], []
    for i, r in enumerate(d["records"], start=1):
        dt = r["date"] if isinstance(r["date"], date) else date.fromisoformat(r["date"])
        rows.append([fdate(dt), dt.strftime("%A"), r["status"].title(), r.get("remarks") or ""])
        extra.append(("TEXTCOLOR", (2, i), (2, i), STATUS_COLORS.get(r["status"], colors.black)))
    story.append(_table(rows, [35 * mm, 35 * mm, 30 * mm, 80 * mm], extra=extra) if len(rows) > 1 else Paragraph("No attendance recorded in this period.", BODY))
    return build(story, f"Attendance - {d['student_name']}")


def section_attendance(d: dict) -> bytes:
    rows, extra = [["Roll", "Name", "Present", "Late", "Absent", "Leave", "Days", "%", "Flag"]], []
    for i, r in enumerate(d["students"], start=1):
        sm = r["summary"]
        rows.append([r["roll_no"], Paragraph(esc(r["full_name"]), CELL), sm.present, sm.late, sm.absent, sm.leave, sm.total_days,
                     f"{sm.percentage}" if sm.percentage is not None else "-", "LOW" if r["low_attendance"] else ""])
        if r["low_attendance"]:
            extra += [("BACKGROUND", (0, i), (-1, i), colors.HexColor("#FDE8E7")), ("TEXTCOLOR", (8, i), (8, i), RED)]
    story = [Paragraph("CLASS ATTENDANCE REPORT", H1), Paragraph(esc(d["section_label"] or ""), CENTER), Spacer(1, 6),
             _info([("Period", f"{fdate(d['from_date'])} - {fdate(d['to_date'])}"), ("Average %", num(d["average_percentage"])),
                    ("Below threshold", f"{d['low_attendance_count']} (under {num(d['threshold'])}%)"), ("Students", str(len(d["students"])))]),
             Spacer(1, 8), _table(rows, [18 * mm, 55 * mm, 18 * mm, 14 * mm, 16 * mm, 15 * mm, 14 * mm, 16 * mm, 14 * mm], extra=extra)]
    return build(story, "Class attendance")


# ============================================================ csv
def to_csv(header: list[str], rows: list[list]) -> bytes:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(header)
    w.writerows(rows)
    return ("﻿" + out.getvalue()).encode("utf-8")        # BOM so Excel opens UTF-8 correctly
