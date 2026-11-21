"""
Operations-modules demo data (Member 2): homework, exams/marks/results, fees, timetable, calendar,
announcements, notifications, complaints.

Run AFTER the foundation seed (`python -m seeds.seed_core`):
    python -m seeds.seed_ops

* Idempotent: every row is looked up by a natural key before insert; notifications are only created together
  with the record they belong to, so re-running never duplicates anything.
* Dates are relative to "today" (school time) so the demo always looks current.
* All people, amounts and incidents are FAKE.
"""
from __future__ import annotations

import random
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.common.scope import audience_user_ids_for_section, parent_user_ids_of_student
from app.common.timeutil import school_today
from app.core.database import SessionLocal
from app.modules.announcements.models import Announcement
from app.modules.announcements.service import dispatch_announcement
from app.modules.calendar.models import Event
from app.modules.complaints.models import Complaint, ComplaintComment
from app.modules.complaints.service import next_ticket
from app.modules.exams.models import Exam, ExamSchedule, GradeScale, Mark
from app.modules.fees.models import FeeHead, FeeInvoice, FeeInvoiceItem, FeePayment, FeeStructure
from app.modules.fees.service import next_number, recompute_status
from app.modules.foundation.models import (
    AcademicYear, Parent, SchoolClass, Section, Student, StudentParent, Subject, Teacher, TeacherAssignment, User,
)
from app.modules.homework.models import Assignment
from app.modules.notifications.service import notify_section, notify_users
from app.modules.timetable.models import PeriodDefinition, TimetableSlot

ZERO = Decimal("0.00")
D = Decimal


def _d(v) -> Decimal:
    return D(str(v)).quantize(D("0.01"))


# ================================================================== reference data
GRADES = [("A+", 90, 100, 4.0, "Outstanding", True), ("A", 80, 89.99, 3.7, "Excellent", True),
          ("B", 70, 79.99, 3.0, "Very good", True), ("C", 60, 69.99, 2.0, "Good", True),
          ("D", 50, 59.99, 1.0, "Satisfactory", True), ("E", 40, 49.99, 0.5, "Needs improvement", True),
          ("F", 0, 39.99, 0.0, "Fail", False)]

PERIODS = [(1, "08:00", "08:40", False, "Period 1"), (2, "08:40", "09:20", False, "Period 2"),
           (3, "09:20", "10:00", False, "Period 3"), (4, "10:00", "10:30", True, "Break"),
           (5, "10:30", "11:10", False, "Period 4"), (6, "11:10", "11:50", False, "Period 5"),
           (7, "11:50", "12:30", False, "Period 6"), (8, "12:30", "13:10", False, "Period 7")]

WEEKLY_JUNIOR = {"MATH": 6, "ENG": 6, "URD": 5, "SCI": 5, "CS": 4, "ISL": 4, "PKS": 4}
WEEKLY_SENIOR = {"MATH": 6, "ENG": 6, "URD": 5, "PHY": 4, "CHEM": 4, "BIO": 4, "CS": 3, "ISL": 3, "PKS": 3}

HOMEWORK_TITLES = {
    "MATH": ["Exercise 5.2 — algebraic expressions", "Revision worksheet: fractions and decimals", "Chapter test preparation"],
    "ENG": ["Essay: My Favourite Season", "Grammar exercise: tenses", "Comprehension passage — questions 1 to 8"],
    "URD": ["Mazmoon: Meri Pasandeeda Shakhsiyat", "Qawaid: Fail aur Fa'il ki mashq", "Nazm ka khulasa likhain"],
    "SCI": ["Diagram: parts of a plant cell", "Short questions — Chapter 4", "Project: states of matter"],
    "PHY": ["Numericals: speed and velocity", "Define Newton's laws with examples", "Lab report: simple pendulum"],
    "CHEM": ["Balance the given equations", "Periodic table — group trends", "Short notes: acids, bases and salts"],
    "BIO": ["Label the human digestive system", "Short questions — Chapter 3", "Observation notes: osmosis experiment"],
    "CS": ["Practice: MS Word table formatting", "Write a flowchart for even/odd numbers", "Short questions: input and output devices"],
    "ISL": ["Seerat: Hijrat-e-Madina (summary)", "Memorize Surah Al-Asr with translation", "Short questions — Chapter 2"],
    "PKS": ["Map work: provinces and capitals", "Essay: Role of Quaid-e-Azam", "Short questions — Chapter 1"],
}

COMPLAINT_ROWS = [
    # (kind, category, subject, description, status, priority, parent_no | student_no | teacher_no, thread)
    ("complaint", "fee", "Fee voucher shows wrong discount", "The sibling discount was not applied on the October voucher for my younger child. Please check and correct it.", "resolved", "normal", ("parent", 1),
     [("admin", "Thank you for reporting this. Accounts is checking the voucher.", False), ("admin", "Discount applied and the voucher has been corrected. JazakAllah.", False)]),
    ("complaint", "facility", "Water cooler not working near Class 8 block", "The water cooler in front of the Class 8 corridor has not been working for a week.", "in_review", "high", ("parent", 5),
     [("admin", "Maintenance has been informed and a technician is scheduled this week.", False), ("admin", "Internal: ask admin office to confirm cooler purchase approval.", True)]),
    ("feedback", "academic", "Appreciation for the Maths teacher", "My son's confidence in Mathematics has improved a lot this term. Thank you to the whole department.", "closed", "low", ("parent", 7),
     [("admin", "Thank you for the kind words. We have shared them with the teacher.", False)]),
    ("suggestion", "other", "Request: Parent-Teacher Meeting on Saturday", "Many working parents cannot attend on weekdays. Could the meeting be held on a Saturday?", "open", "normal", ("parent", 12), []),
    ("complaint", "transport", "Van arrives late in the morning", "The school van for Hassan Abdal city route is arriving 15 minutes late almost every day.", "in_review", "normal", ("parent", 20),
     [("admin", "We have asked the transport in-charge for a written explanation.", False)]),
    ("complaint", "teacher", "Too much homework on weekends", "Students in Class 9 receive homework from 5 subjects every Friday. Please balance the workload.", "open", "normal", ("parent", 25), []),
    ("feedback", "facility", "Library timing is excellent", "The extended library hours before exams helped my daughter a lot.", "resolved", "low", ("student", 11),
     [("admin", "Glad to hear this! We will keep the extended hours during exams.", False)]),
    ("suggestion", "facility", "More computers in the lab", "Two students share one computer in the lab. More systems would help during practicals.", "in_review", "normal", ("student", 20),
     [("admin", "Noted. The proposal has been forwarded to the management.", False)]),
    ("complaint", "other", "Projector in staff room needs repair", "The projector used for staff presentations has a flickering display.", "open", "low", ("teacher", 4), []),
    ("suggestion", "academic", "Extra revision classes before midterm", "Suggesting two extra revision periods per week for Class 10 before exams.", "resolved", "normal", ("teacher", 2),
     [("admin", "Approved. Revision periods were added after school on Tuesday and Thursday.", False)]),
]


def _rng(*key) -> random.Random:
    return random.Random("|".join(str(k) for k in key))


# ================================================================== helpers
class Ctx:
    def __init__(self, db: Session):
        self.db = db
        self.today = school_today()
        self.year = db.scalar(select(AcademicYear).where(AcademicYear.is_current))
        if self.year is None:
            raise SystemExit("No current academic year. Run `python -m seeds.seed_core` first.")
        self.admin = db.scalar(select(User).where(User.login_id == "admin"))
        if self.admin is None:
            raise SystemExit("Foundation data missing. Run `python -m seeds.seed_core` first.")
        self.subjects = {s.code: s for s in db.scalars(select(Subject))}
        self.classes = {c.name: c for c in db.scalars(select(SchoolClass))}
        self.sections = {}  # "8-A" -> Section
        for sec, cls in db.execute(select(Section, SchoolClass).join(SchoolClass, SchoolClass.id == Section.class_id)).all():
            self.sections[f"{cls.grade_level}-{sec.name}"] = sec
        self.section_label = {s.id: k for k, s in self.sections.items()}
        self.section_class = {s.id: s.class_id for s in self.sections.values()}
        self.students = defaultdict(list)  # section_id -> [Student]
        for st in db.scalars(select(Student).where(Student.is_active).order_by(Student.roll_no)):
            self.students[st.section_id].append(st)
        self.assign = defaultdict(dict)  # section_id -> {subject_code: Teacher}
        teachers = {t.id: t for t in db.scalars(select(Teacher))}
        code_of = {s.id: s.code for s in self.subjects.values()}
        for ta in db.scalars(select(TeacherAssignment).where(TeacherAssignment.academic_year_id == self.year.id)):
            self.assign[ta.section_id][code_of[ta.subject_id]] = teachers[ta.teacher_id]
        self.teacher_by_no = {}
        for no in range(1, 11):
            u = db.scalar(select(User).where(User.login_id == f"teacher{no}"))
            if u:
                self.teacher_by_no[no] = (u, db.scalar(select(Teacher).where(Teacher.user_id == u.id)))

    def user(self, login: str) -> User | None:
        return self.db.scalar(select(User).where(User.login_id == login))

    def student_no(self, n: int) -> Student | None:
        u = self.user(f"student{n}")
        return self.db.scalar(select(Student).where(Student.user_id == u.id)) if u else None

    def teacher_user(self, teacher: Teacher) -> User:
        return self.db.get(User, teacher.user_id)


def _workday(d: date, step: int = 0) -> date:
    """d moved forward `step` working days (Mon-Sat school week), skipping Sundays."""
    while step > 0:
        d += timedelta(days=1)
        if d.weekday() != 6:
            step -= 1
    while d.weekday() == 6:
        d += timedelta(days=1)
    return d


# ================================================================== modules
def seed_grade_scale(c: Ctx) -> int:
    if c.db.scalar(select(func.count()).select_from(GradeScale)):
        return 0
    for g, lo, hi, gpa, remark, ok in GRADES:
        c.db.add(GradeScale(grade=g, min_percentage=_d(lo), max_percentage=_d(hi), gpa_points=_d(gpa), remark=remark, is_pass=ok))
    return len(GRADES)


def seed_timetable(c: Ctx) -> dict:
    db = c.db
    periods = {}
    for no, st, en, brk, label in PERIODS:
        p = db.scalar(select(PeriodDefinition).where(PeriodDefinition.period_no == no))
        if p is None:
            p = PeriodDefinition(period_no=no, start_time=time.fromisoformat(st), end_time=time.fromisoformat(en),
                                 is_break=brk, label=label)
            db.add(p)
            db.flush()
        periods[no] = p
    teach_nos = [n for n, p in sorted(periods.items()) if not p.is_break]
    busy = set()  # (teacher_id, day, period_no) across sections
    for slot, in db.execute(select(TimetableSlot).where(TimetableSlot.academic_year_id == c.year.id)).all():
        pno = next(n for n, p in periods.items() if p.id == slot.period_id)
        busy.add((slot.teacher_id, slot.day_of_week, pno))
    created = skipped = unplaced = 0
    for label in sorted(c.sections):
        sec = c.sections[label]
        if db.scalar(select(TimetableSlot.id).where(TimetableSlot.section_id == sec.id,
                                                      TimetableSlot.academic_year_id == c.year.id).limit(1)):
            skipped += 1
            continue
        weekly = WEEKLY_JUNIOR if sec.class_id in (c.classes["Class 6"].id, c.classes["Class 7"].id) else WEEKLY_SENIOR
        lessons = []  # round-robin so subjects spread across the week
        remaining = dict(weekly)
        while any(remaining.values()):
            for code in weekly:
                if remaining[code]:
                    lessons.append(code)
                    remaining[code] -= 1
        grid = {}
        by_day_subject = set()
        rng = _rng("timetable", label)
        cells = [(d, p) for p in teach_nos for d in range(1, 7)]
        for code in lessons:
            teacher = c.assign[sec.id].get(code)
            if teacher is None:
                continue
            order = cells[:]
            rng.shuffle(order)
            placed = False
            for relax in (False, True):
                for d, p in order:
                    if (d, p) in grid or (teacher.id, d, p) in busy:
                        continue
                    if not relax and (d, code) in by_day_subject:
                        continue
                    grid[(d, p)] = (code, teacher)
                    busy.add((teacher.id, d, p))
                    by_day_subject.add((d, code))
                    placed = True
                    break
                if placed:
                    break
            if not placed:
                unplaced += 1
        for (d, p), (code, teacher) in sorted(grid.items()):
            room = f"Room {c.section_label[sec.id].replace('-', '')}"
            if code == "CS":
                room = "Computer Lab"
            elif code in ("PHY", "CHEM", "BIO") and p % 2 == 0:
                room = "Science Lab"
            db.add(TimetableSlot(academic_year_id=c.year.id, section_id=sec.id, subject_id=c.subjects[code].id,
                                 teacher_id=teacher.id, day_of_week=d, period_id=periods[p].id, room=room))
            created += 1
    db.flush()
    return {"slots_created": created, "sections_skipped": skipped, "unplaced_lessons": unplaced}


def seed_homework(c: Ctx) -> int:
    db, created = c.db, 0
    for label, sec in sorted(c.sections.items()):
        for code, teacher in sorted(c.assign[sec.id].items()):
            titles = HOMEWORK_TITLES[code]
            rng = _rng("hw", label, code)
            plan = [  # (title idx, assigned offset, due offset, status, max_marks)
                (0, -14, -7, "closed", 20), (1, -3, rng.randint(2, 5), "published", 10),
                (2, -1, rng.randint(6, 10), "published", None),
            ]
            if rng.random() < 0.25:
                plan.append((0, 0, 14, "draft", 25))
            for idx, a_off, d_off, status, mm in plan:
                title = titles[idx] + (" (draft)" if status == "draft" else "")
                if db.scalar(select(Assignment.id).where(Assignment.section_id == sec.id, Assignment.subject_id == c.subjects[code].id,
                                                          Assignment.title == title)):
                    continue
                a = Assignment(teacher_id=teacher.id, section_id=sec.id, subject_id=c.subjects[code].id, title=title,
                               description=f"Complete in your notebook and submit to your {c.subjects[code].name} teacher. "
                                           f"Neat handwriting and proper headings are required.",
                               assigned_date=c.today + timedelta(days=a_off), due_date=c.today + timedelta(days=d_off),
                               max_marks=_d(mm) if mm else None, status=status)
                db.add(a)
                db.flush()
                created += 1
                if status == "published" and a_off >= -3:
                    notify_section(db, sec.id, f"New homework: {c.subjects[code].name}",
                                   f"{a.title} — due {a.due_date.strftime('%d %b %Y')}", "homework",
                                   reference_type="assignment", reference_id=a.id)
    return created


def _exam(c: Ctx, name: str, etype: str, start: date, end: date, status: str) -> tuple[Exam, bool]:
    e = c.db.scalar(select(Exam).where(Exam.name == name, Exam.academic_year_id == c.year.id))
    if e is not None:
        return e, False
    e = Exam(name=name, exam_type=etype, academic_year_id=c.year.id, start_date=start, end_date=end, status="draft")
    c.db.add(e)
    c.db.flush()
    return e, True


def _papers(c: Ctx, exam: Exam, sections: list[str], total: int, passing: int, start_hour: int = 9) -> list[ExamSchedule]:
    out = []
    for label in sections:
        sec = c.sections[label]
        codes = list(c.assign[sec.id].keys())
        order = ["ENG", "MATH", "URD", "SCI", "PHY", "CHEM", "BIO", "ISL", "PKS", "CS"]
        codes.sort(key=order.index)
        for i, code in enumerate(codes):
            d = _workday(exam.start_date, i)
            if d > exam.end_date:
                d = exam.end_date
            if c.db.scalar(select(ExamSchedule.id).where(ExamSchedule.exam_id == exam.id, ExamSchedule.section_id == sec.id,
                                                          ExamSchedule.subject_id == c.subjects[code].id)):
                continue
            # one paper per day per section: spread across the window when it is short
            s = ExamSchedule(exam_id=exam.id, section_id=sec.id, subject_id=c.subjects[code].id, exam_date=d,
                             start_time=time(start_hour + (i % 2), 0), end_time=time(start_hour + (i % 2) + 2 if total > 50 else start_hour + (i % 2) + 1, 0),
                             room=f"Hall {1 + (sec.name == 'B')}", total_marks=_d(total), passing_marks=_d(passing))
            c.db.add(s)
            out.append(s)
    c.db.flush()
    return out


def _enter_marks(c: Ctx, exam: Exam, papers: list[ExamSchedule]) -> int:
    n = 0
    for s in papers:
        teacher = next((t for t in c.assign[s.section_id].values()), None)
        code = next(k for k, v in c.subjects.items() if v.id == s.subject_id)
        teacher = c.assign[s.section_id][code]
        entered_by = teacher.user_id
        for st in c.students[s.section_id]:
            ability = _rng("ability", st.roll_no).uniform(0.38, 0.97)
            r = _rng("mark", exam.name, st.roll_no, code)
            if r.random() < 0.03:
                c.db.add(Mark(exam_schedule_id=s.id, student_id=st.id, marks_obtained=None, is_absent=True,
                              remarks="Absent (medical)", entered_by=entered_by))
                n += 1
                continue
            pct = min(1.0, max(0.12, ability + r.uniform(-0.12, 0.10)))
            obtained = _d(round(float(s.total_marks) * pct * 2) / 2)  # nearest half mark
            c.db.add(Mark(exam_schedule_id=s.id, student_id=st.id, marks_obtained=obtained, is_absent=False, entered_by=entered_by))
            n += 1
    c.db.flush()
    return n


def seed_exams(c: Ctx) -> dict:
    db, out = c.db, {}
    all_secs = sorted(c.sections)
    # 1. Mid-term: finished, marks entered, results published
    mid, new = _exam(c, "Mid-Term Examination 2026", "midterm", c.today - timedelta(days=40), c.today - timedelta(days=27), "results_published")
    if new:
        papers = _papers(c, mid, all_secs, 100, 33)
        out["midterm_marks"] = _enter_marks(c, mid, papers)
        mid.status = "results_published"
        for label in all_secs:
            notify_section(db, c.sections[label].id, f"Results published: {mid.name}",
                           f"The results of {mid.name} are now available.", "marks", reference_type="exam", reference_id=mid.id)
    # 2. Monthly test: finished, marks entered, awaiting publication (admin can publish from the UI)
    mon, new = _exam(c, "Monthly Test — October 2026", "monthly", c.today - timedelta(days=8), c.today - timedelta(days=3), "completed")
    if new:
        papers = _papers(c, mon, ["8-A", "8-B", "9-A"], 50, 17)
        out["monthly_marks"] = _enter_marks(c, mon, papers)
        mon.status = "completed"
    # 3. Final term: scheduled in the future (papers set, no marks yet)
    fin, new = _exam(c, "Final Term Examination 2026-27", "final", c.today + timedelta(days=120), c.today + timedelta(days=134), "scheduled")
    if new:
        _papers(c, fin, ["8-A", "9-A", "10-A"], 100, 33)
        fin.status = "scheduled"
    # 4. Pre-board mock: draft
    _exam(c, "Pre-Board Mock Exam", "other", c.today + timedelta(days=60), c.today + timedelta(days=70), "draft")
    db.flush()
    return out


# ------------------------------------------------------------------ fees
HEADS = [("Tuition Fee", "monthly"), ("Computer Lab Fee", "monthly"), ("Annual Charges", "yearly"),
         ("Examination Fee", "quarterly"), ("Admission Fee", "one_time")]
TUITION = {6: 3500, 7: 3800, 8: 4200, 9: 4800, 10: 5200}


def seed_fee_structure(c: Ctx) -> dict:
    db = c.db
    heads = {}
    for name, freq in HEADS:
        h = db.scalar(select(FeeHead).where(func.lower(FeeHead.name) == name.lower()))
        if h is None:
            h = FeeHead(name=name, frequency=freq)
            db.add(h)
            db.flush()
        heads[name] = h
    n = 0
    for cname, cls in c.classes.items():
        grade = int(cname.split()[-1])
        amounts = {"Tuition Fee": TUITION[grade], "Computer Lab Fee": 500, "Annual Charges": 4000 + (grade - 6) * 500,
                   "Examination Fee": 1200, "Admission Fee": 5000}
        for hname, amount in amounts.items():
            if db.scalar(select(FeeStructure.id).where(FeeStructure.class_id == cls.id, FeeStructure.fee_head_id == heads[hname].id,
                                                        FeeStructure.academic_year_id == c.year.id)) is None:
                db.add(FeeStructure(class_id=cls.id, fee_head_id=heads[hname].id, academic_year_id=c.year.id, amount=_d(amount)))
                n += 1
    db.flush()
    return {"heads": heads, "structures": n}


def _month_start(today: date, back: int) -> date:
    y, m = today.year, today.month - back
    while m < 1:
        m += 12
        y -= 1
    return date(y, m, 1)


def _pay(c: Ctx, inv: FeeInvoice, amount: Decimal, when: date, method: str, ref: str | None = None) -> FeePayment:
    p = FeePayment(receipt_no=next_number(c.db, "receipt_no_seq", "RCP"), invoice_id=inv.id, amount=amount,
                   payment_date=min(when, c.today), method=method, reference=ref, recorded_by=c.admin.id,
                   remarks=None)
    c.db.add(p)
    inv.paid_amount = D(inv.paid_amount) + amount
    recompute_status(inv)
    return p


def seed_fees(c: Ctx) -> dict:
    db = c.db
    info = seed_fee_structure(c)
    heads = info["heads"]
    # (period label, month offset back, paid share, partial share)
    periods = [(_month_start(c.today, 2), 0.92, 0.04), (_month_start(c.today, 1), 0.60, 0.20), (_month_start(c.today, 0), 0.35, 0.15)]
    methods = ["cash", "cash", "bank_transfer", "cheque", "cash", "bank_transfer"]
    stats = {"invoices": 0, "payments": 0}
    all_students = [s for secid in c.students for s in c.students[secid]]
    sibling_users = set()
    for st in sorted(all_students, key=lambda s: s.roll_no):
        parents = db.scalars(select(StudentParent.parent_id).where(StudentParent.parent_id.in_(
            select(StudentParent.parent_id).where(StudentParent.student_id == st.id)))).all()
        if len(parents) > 1:
            sibling_users.add(st.id)
    for start, paid_share, partial_share in periods:
        label = start.strftime("%B %Y")
        issue, due = start, start.replace(day=10)
        for st in sorted(all_students, key=lambda s: s.roll_no):
            if db.scalar(select(FeeInvoice.id).where(FeeInvoice.student_id == st.id, FeeInvoice.period_label == label)):
                continue
            grade = int(c.section_label[st.section_id].split("-")[0])
            items = [(heads["Tuition Fee"].id, "Tuition Fee", _d(TUITION[grade])), (heads["Computer Lab Fee"].id, "Computer Lab Fee", _d(500))]
            total = sum((a for _, _, a in items), ZERO)
            discount = _d(500) if st.id in sibling_users else ZERO
            inv = FeeInvoice(invoice_no=next_number(db, "invoice_no_seq", "INV"), student_id=st.id, academic_year_id=c.year.id,
                             period_label=label, issue_date=issue, due_date=due, total_amount=total, discount_amount=discount,
                             paid_amount=ZERO, status="unpaid")
            db.add(inv)
            db.flush()
            db.add_all(FeeInvoiceItem(invoice_id=inv.id, fee_head_id=h, description=d, amount=a) for h, d, a in items)
            stats["invoices"] += 1
            r = _rng("fee", st.roll_no, label)
            roll = r.random()
            net = total - discount
            method = r.choice(methods)
            if roll < paid_share:
                _pay(c, inv, net, due - timedelta(days=r.randint(0, 8)), method, f"BT-{r.randint(100000, 999999)}" if method == "bank_transfer" else None)
                stats["payments"] += 1
            elif roll < paid_share + partial_share:
                part = _d(round(float(net) * r.choice([0.3, 0.5, 0.6]) / 100) * 100)
                if 0 < part < net:
                    _pay(c, inv, part, due - timedelta(days=r.randint(0, 5)), method)
                    stats["payments"] += 1
            if issue >= c.today - timedelta(days=c.today.day):  # current month: notify parents
                notify_users(db, parent_user_ids_of_student(db, st.id), f"Fee invoice {inv.invoice_no}",
                             f"{st.full_name}: {inv.period_label} fee of PKR {net:,.0f} is due on {due.strftime('%d %b %Y')}.",
                             "fee", "fee_invoice", inv.id)
    # Annual charges (yearly head), issued in April: mostly paid
    alabel = "Annual Charges 2026-27"
    for st in sorted(all_students, key=lambda s: s.roll_no):
        if db.scalar(select(FeeInvoice.id).where(FeeInvoice.student_id == st.id, FeeInvoice.period_label == alabel)):
            continue
        grade = int(c.section_label[st.section_id].split("-")[0])
        amt = _d(4000 + (grade - 6) * 500)
        inv = FeeInvoice(invoice_no=next_number(db, "invoice_no_seq", "INV"), student_id=st.id, academic_year_id=c.year.id,
                         period_label=alabel, issue_date=date(2026, 4, 1), due_date=date(2026, 4, 30), total_amount=amt,
                         discount_amount=ZERO, paid_amount=ZERO, status="unpaid")
        db.add(inv)
        db.flush()
        db.add(FeeInvoiceItem(invoice_id=inv.id, fee_head_id=heads["Annual Charges"].id, description="Annual Charges", amount=amt))
        stats["invoices"] += 1
        r = _rng("annual", st.roll_no)
        x = r.random()
        if x < 0.85:
            _pay(c, inv, amt, date(2026, 4, r.randint(2, 28)), r.choice(methods))
            stats["payments"] += 1
        elif x < 0.93:
            _pay(c, inv, _d(2000), date(2026, 5, 10), "cash")
            stats["payments"] += 1
    # One cancelled invoice and one reversed payment, to demonstrate those workflows
    st48 = c.student_no(48)
    if st48 and not db.scalar(select(FeeInvoice.id).where(FeeInvoice.student_id == st48.id, FeeInvoice.period_label == "Late Admission 2026")):
        inv = FeeInvoice(invoice_no=next_number(db, "invoice_no_seq", "INV"), student_id=st48.id, academic_year_id=c.year.id,
                         period_label="Late Admission 2026", issue_date=c.today - timedelta(days=20), due_date=c.today - timedelta(days=10),
                         total_amount=_d(5000), discount_amount=ZERO, paid_amount=ZERO, status="cancelled")
        db.add(inv)
        db.flush()
        db.add(FeeInvoiceItem(invoice_id=inv.id, fee_head_id=heads["Admission Fee"].id, description="Admission Fee", amount=_d(5000)))
        stats["invoices"] += 1
    st3 = c.student_no(3)
    if st3:
        label = _month_start(c.today, 1).strftime("%B %Y")
        inv = db.scalar(select(FeeInvoice).where(FeeInvoice.student_id == st3.id, FeeInvoice.period_label == label))
        if inv is not None and not db.scalar(select(FeePayment.id).where(FeePayment.invoice_id == inv.id, FeePayment.is_reversal)):
            for p in db.scalars(select(FeePayment).where(FeePayment.invoice_id == inv.id)):  # reset, then replay the story
                db.delete(p)
            db.flush()
            inv.paid_amount, inv.status = ZERO, "unpaid"
            wrong = _pay(c, inv, _d(2000), inv.issue_date + timedelta(days=5), "cash")
            db.flush()
            db.add(FeePayment(receipt_no=next_number(db, "receipt_no_seq", "REV"), invoice_id=inv.id, amount=wrong.amount,
                              payment_date=min(inv.issue_date + timedelta(days=6), c.today), method="cash", reference=wrong.receipt_no,
                              remarks="Entered against the wrong student by mistake", recorded_by=c.admin.id, is_reversal=True,
                              reversal_of_id=wrong.id))
            inv.paid_amount = ZERO
            _pay(c, inv, D(inv.total_amount) - D(inv.discount_amount), inv.issue_date + timedelta(days=7), "bank_transfer", "BT-482913")
    db.flush()
    return stats


# ------------------------------------------------------------------ calendar
def _event(c: Ctx, title: str, start: date, **kw) -> bool:
    if c.db.scalar(select(Event.id).where(Event.title == title, Event.start_date == start)):
        return False
    end = kw.pop("end", start)
    c.db.add(Event(title=title, start_date=start, end_date=end, created_by=c.admin.id, **kw))
    return True


def seed_calendar(c: Ctx) -> int:
    t, n = c.today, 0
    y = t.year
    events = [
        ("Iqbal Day (Public Holiday)", date(y, 11, 9), dict(event_type="holiday", description="School closed on Iqbal Day.")),
        ("Parent-Teacher Meeting", t + timedelta(days=9), dict(event_type="meeting", start_time=time(9, 0), end_time=time(13, 0), location="School Main Hall", audience="parents",
                                                                  description="Meet class teachers and discuss mid-term performance. Please bring the child's diary.")),
        ("Science Exhibition", t + timedelta(days=16), dict(event_type="activity", start_time=time(10, 0), end_time=time(14, 0), location="School Ground",
                                                              description="Students of classes 6-10 display science projects. Parents are welcome.")),
        ("Class 8-A Educational Trip — Taxila Museum", t + timedelta(days=12), dict(event_type="activity", audience="class", section_id=c.sections["8-A"].id,
                                                                                    start_time=time(8, 0), end_time=time(14, 0), location="Taxila Museum",
                                                                                    description="Signed permission slip required. Transport provided by the school.")),
        ("Inter-House Sports Day", t + timedelta(days=24), dict(event_type="sports", end=t + timedelta(days=25), start_time=time(9, 0), location="School Ground",
                                                                 description="Races, relay, tug of war and prize distribution.")),
        ("Staff Meeting — Result Analysis", t + timedelta(days=3), dict(event_type="meeting", audience="teachers", start_time=time(13, 30), end_time=time(14, 30), location="Staff Room")),
        ("Quaid-e-Azam Day / Christmas (Public Holiday)", date(y, 12, 25), dict(event_type="holiday")),
        ("Winter Vacations", date(y, 12, 28), dict(event_type="holiday", end=date(y + 1, 1, 8), description="School reopens after the winter break.")),
        ("Kashmir Solidarity Day", date(y + 1, 2, 5), dict(event_type="holiday")),
        ("Pakistan Day (Public Holiday)", date(y + 1, 3, 23), dict(event_type="holiday")),
        ("Independence Day Ceremony", date(y, 8, 14), dict(event_type="activity", start_time=time(8, 30), location="School Ground", description="Flag hoisting and national songs.")),
        ("Mid-Term Examination", t - timedelta(days=40), dict(event_type="exam", end=t - timedelta(days=27), audience="all")),
        ("Final Term Examination", t + timedelta(days=120), dict(event_type="exam", end=t + timedelta(days=134), audience="all")),
        ("Quran Recitation Competition", t + timedelta(days=6), dict(event_type="activity", audience="students", start_time=time(11, 0), location="Assembly Hall")),
    ]
    for title, start, kw in events:
        n += _event(c, title, start, **kw)
    c.db.flush()
    return n


# ------------------------------------------------------------------ announcements
def seed_announcements(c: Ctx) -> int:
    db, n = c.db, 0
    now = datetime.now(timezone.utc)
    rows = [
        dict(title="Mid-term results are now available", body="The results of the Mid-Term Examination 2026 have been published. Parents can view them in the app under Results.",
             audience="all", priority="important", publish_at=now - timedelta(days=22)),
        dict(title="Winter school timings from next week", body="Due to the cold weather the school timings will be 8:30 AM to 1:30 PM from Monday. Please ensure students wear the winter uniform.",
             audience="all", priority="normal", publish_at=now - timedelta(days=2)),
        dict(title="Fee reminder — October dues", body="Parents are requested to clear the October fee dues before the 10th to avoid a late fee. Contact the accounts office for any query.",
             audience="parents", priority="important", publish_at=now - timedelta(days=1)),
        dict(title="Staff meeting: result analysis", body="All teachers are requested to attend the staff meeting on result analysis in the staff room at 1:30 PM.",
             audience="teachers", priority="normal", publish_at=now - timedelta(hours=20)),
        dict(title="Class 8-A trip: permission slips", body="Please return the signed permission slip for the Taxila Museum trip by Thursday. Students without a slip cannot join the trip.",
             audience="class", section_id=c.sections["8-A"].id, class_id=c.sections["8-A"].class_id, priority="important", publish_at=now - timedelta(hours=6)),
        dict(title="Fog advisory — van drivers and parents", body="Dense fog is expected in the early mornings. Vans may run 10–15 minutes late. Please do not send children alone.",
             audience="all", priority="urgent", publish_at=now - timedelta(hours=3), expires_at=now + timedelta(days=7)),
        dict(title="Science exhibition — project registration", body="Students who want to participate in the Science Exhibition should register their project with their science teacher by next Monday.",
             audience="students", priority="normal", publish_at=now - timedelta(days=1, hours=2)),
        dict(title="Summer vacation notice (old)", body="Summer vacations were from 1 July to 31 August. School has reopened.", audience="all", priority="normal",
             publish_at=now - timedelta(days=60), expires_at=now - timedelta(days=30), status="archived"),
        dict(title="Annual Sports Day — draft schedule", body="Draft: events list and house colours. To be finalised after the sports committee meeting.", audience="all",
             priority="normal", status="draft", publish_at=now + timedelta(days=5)),
    ]
    for r in rows:
        if db.scalar(select(Announcement.id).where(Announcement.title == r["title"])):
            continue
        status = r.pop("status", "published")
        a = Announcement(created_by=c.admin.id, status=status, **r)
        db.add(a)
        db.flush()
        n += 1
        if status == "published" and a.publish_at <= now:
            dispatch_announcement(db, a)
    return n


# ------------------------------------------------------------------ complaints
def seed_complaints(c: Ctx) -> int:
    db, n = c.db, 0
    for kind, cat, subject, desc, status, prio, (who, no), thread in COMPLAINT_ROWS:
        u = c.user(f"{who}{no}")
        if u is None or db.scalar(select(Complaint.id).where(Complaint.submitted_by == u.id, Complaint.subject == subject)):
            continue
        student_id = None
        if who == "parent":
            p = db.scalar(select(Parent).where(Parent.user_id == u.id))
            student_id = db.scalar(select(StudentParent.student_id).where(StudentParent.parent_id == p.id).limit(1))
        elif who == "student":
            student_id = db.scalar(select(Student.id).where(Student.user_id == u.id))
        age = _rng("complaint", subject).randint(2, 25)
        created = datetime.now(timezone.utc) - timedelta(days=age)
        cp = Complaint(ticket_no=next_ticket(db), submitted_by=u.id, student_id=student_id, category=cat, kind=kind, subject=subject,
                       description=desc, status="open", priority=prio, assigned_to=c.admin.id if status != "open" else None,
                       created_at=created, updated_at=created)
        db.add(cp)
        db.flush()
        n += 1
        step = timedelta(hours=7)
        for i, (author, msg, internal) in enumerate(thread, 1):
            at = created + step * i
            db.add(ComplaintComment(complaint_id=cp.id, author_id=c.admin.id, message=msg, is_internal=internal, created_at=at, updated_at=at))
        # "status history": a system-style comment per transition so the thread shows how it moved
        path = ["open", "in_review", "resolved", "closed"]
        for i, s in enumerate(path[1:path.index(status) + 1], 1):
            at = created + timedelta(days=i)
            db.add(ComplaintComment(complaint_id=cp.id, author_id=c.admin.id, message=f"Status changed to {s.replace('_', ' ')}.",
                                    is_internal=False, created_at=at, updated_at=at))
        cp.status, cp.updated_at = status, created + timedelta(days=max(1, path.index(status)))
        if status != "open":
            notify_users(db, [u.id], f"Ticket {cp.ticket_no}: {status.replace('_', ' ').title()}",
                         f"The status of your {kind} \"{subject}\" is now {status.replace('_', ' ')}.", "complaint", "complaint", cp.id)
    return n


def _age_notifications(c: Ctx) -> int:
    """Mark a deterministic ~40% of notifications as read so both states appear in the UI (only on first run)."""
    db = c.db
    from app.modules.notifications.models import Notification
    if db.scalar(select(func.count()).select_from(Notification).where(Notification.is_read)):
        return 0
    ids = list(db.scalars(select(Notification.id).order_by(Notification.id)))
    chosen = [i for i in ids if _rng("read", i).random() < 0.4]
    if chosen:
        db.execute(update(Notification).where(Notification.id.in_(chosen)).values(is_read=True, read_at=func.now()))
    return len(chosen)


# ================================================================== entry point
def run(db: Session | None = None) -> dict:
    own = db is None
    db = db or SessionLocal()
    try:
        c = Ctx(db)
        stats = {"grade_bands": seed_grade_scale(c)}
        stats["timetable"] = seed_timetable(c)
        stats["assignments"] = seed_homework(c)
        stats["exams"] = seed_exams(c)
        stats["fees"] = seed_fees(c)
        stats["events"] = seed_calendar(c)
        stats["announcements"] = seed_announcements(c)
        stats["complaints"] = seed_complaints(c)
        db.flush()
        stats["notifications_marked_read"] = _age_notifications(c)
        db.commit()
        return stats
    except Exception:
        db.rollback()
        raise
    finally:
        if own:
            db.close()


if __name__ == "__main__":
    print(run())
