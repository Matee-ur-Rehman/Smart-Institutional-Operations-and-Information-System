"""Default data for Member 2's modules: grade scale, fee heads and fees per class, period timings,
public holidays, and a little sample content (one homework, one announcement, a Class 8-A timetable).

Needs the shared foundation to be seeded first (python -m seeds.seed_core, or Faizan's seed): a current
academic year, classes, sections, subjects, an admin user and, for the samples, a teacher assigned to
English/Mathematics/Science/Urdu in Class 8-A.

Run from backend/:   python -m seeds.seed_ops
Safe to run twice. Every amount, grade band and timing below is a DEFAULT to be customised for the school.
No notifications are created by seeding.
"""
import sys
from datetime import date, time, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.modules.announcements.models import Announcement
from app.modules.exams.models import GradeScale
from app.modules.fees.models import FeeHead, FeeStructure
from app.modules.homework.models import Assignment
from app.modules.ops_common.base import utcnow
from app.modules.ops_common.core_refs import AcademicYear, SchoolClass, Section, Subject, User
from app.modules.ops_common.scope import teacher_for_subject
from app.modules.school_calendar.models import Event
from app.modules.timetable.models import PeriodDefinition, TimetableSlot

GRADES = [  # grade, min %, max %, gpa, remark, is_pass
    ("A+", "90.00", "100.00", "4.00", "Outstanding", True),
    ("A", "80.00", "89.99", "3.50", "Excellent", True),
    ("B", "70.00", "79.99", "3.00", "Very good", True),
    ("C", "60.00", "69.99", "2.50", "Good", True),
    ("D", "50.00", "59.99", "2.00", "Satisfactory", True),
    ("E", "40.00", "49.99", "1.00", "Pass", True),
    ("F", "0.00", "39.99", "0.00", "Fail", False),
]
FEE_HEADS = [("Tuition Fee", "monthly"), ("Admission Fee", "one_time"), ("Annual Charges", "yearly"), ("Examination Fee", "quarterly")]
PERIODS = [  # period_no, label, start, end, is_break
    (1, "Period 1", time(8, 0), time(8, 40), False),
    (2, "Period 2", time(8, 40), time(9, 20), False),
    (3, "Period 3", time(9, 20), time(10, 0), False),
    (4, "Break", time(10, 0), time(10, 20), True),
    (5, "Period 4", time(10, 20), time(11, 0), False),
    (6, "Period 5", time(11, 0), time(11, 40), False),
    (7, "Period 6", time(11, 40), time(12, 20), False),
]


def tuition_for(grade_level: int) -> Decimal:
    return Decimal(2000 + 250 * grade_level)  # Class 1 = 2,250 ... Class 10 = 4,500 (placeholder amounts)


def run(db: Session) -> dict:
    """Seed Member 2's default data. Flushes but does not commit: the caller commits."""
    created: dict = {}

    def bump(key: str) -> None:
        created[key] = created.get(key, 0) + 1

    year = db.scalar(select(AcademicYear).where(AcademicYear.is_current.is_(True)))
    admin = db.scalar(select(User).where(User.role == "admin").order_by(User.created_at))
    if year is None or admin is None:
        raise RuntimeError("Seed the shared foundation first: python -m seeds.seed_core (needs a current academic year and an admin)")

    if db.scalar(select(GradeScale.id).limit(1)) is None:
        for grade, low, high, gpa, remark, is_pass in GRADES:
            db.add(GradeScale(grade=grade, min_percentage=Decimal(low), max_percentage=Decimal(high), gpa_points=Decimal(gpa), remark=remark, is_pass=is_pass))
            bump("grade_scales")

    heads = {}
    for name, frequency in FEE_HEADS:
        head = db.scalar(select(FeeHead).where(FeeHead.name == name))
        if head is None:
            head = FeeHead(name=name, frequency=frequency)
            db.add(head)
            db.flush()
            bump("fee_heads")
        heads[name] = head
    amounts = {"Admission Fee": lambda g: Decimal(5000), "Annual Charges": lambda g: Decimal(3000), "Examination Fee": lambda g: Decimal(500), "Tuition Fee": tuition_for}
    for school_class in db.scalars(select(SchoolClass).where(SchoolClass.is_active.is_(True))):
        for name, head in heads.items():
            exists = db.scalar(select(FeeStructure.id).where(
                FeeStructure.class_id == school_class.id, FeeStructure.fee_head_id == head.id, FeeStructure.academic_year_id == year.id))
            if exists is None:
                db.add(FeeStructure(class_id=school_class.id, fee_head_id=head.id, academic_year_id=year.id, amount=amounts[name](school_class.grade_level)))
                bump("fee_structures")

    periods = {}
    for no, label, start, end, is_break in PERIODS:
        period = db.scalar(select(PeriodDefinition).where(PeriodDefinition.period_no == no))
        if period is None:
            period = PeriodDefinition(period_no=no, label=label, start_time=start, end_time=end, is_break=is_break)
            db.add(period)
            db.flush()
            bump("period_definitions")
        periods[no] = period

    start_year = year.start_date.year
    for title, event_date, kind in [
        ("Independence Day", date(start_year, 8, 14), "holiday"),
        ("Iqbal Day", date(start_year, 11, 9), "holiday"),
        ("Quaid-e-Azam Day", date(start_year, 12, 25), "holiday"),
        ("Pakistan Day", date(start_year + 1, 3, 23), "holiday"),
    ]:
        if db.scalar(select(Event.id).where(Event.title == title, Event.start_date == event_date)) is None:
            db.add(Event(title=title, event_type=kind, start_date=event_date, end_date=event_date, audience="all", created_by=admin.id))
            bump("events")

    welcome = "Welcome to the new session"
    if db.scalar(select(Announcement.id).where(Announcement.title == welcome)) is None:
        db.add(Announcement(
            title=welcome, body="Classes run Monday to Saturday. Please check the app for the timetable and homework.",
            audience="all", priority="normal", status="published", publish_at=utcnow(), created_by=admin.id,
        ))
        bump("announcements")

    # ---- samples for Class 8-A (only when the foundation seed assigned its teachers) ----
    section = db.scalar(
        select(Section).join(SchoolClass, SchoolClass.id == Section.class_id).where(SchoolClass.name == "Class 8", Section.name == "A")
    )
    subjects = {s.code: s for s in db.scalars(select(Subject))}
    if section is not None and {"ENG", "MAT", "SCI", "URD"} <= subjects.keys():
        teachers = {code: teacher_for_subject(db, section.id, subjects[code].id) for code in ("ENG", "MAT", "SCI", "URD")}
        if all(teachers.values()):
            title = "Reading comprehension: Unit 1"
            if db.scalar(select(Assignment.id).where(Assignment.title == title, Assignment.section_id == section.id)) is None:
                db.add(Assignment(
                    teacher_id=teachers["ENG"], section_id=section.id, subject_id=subjects["ENG"].id, title=title,
                    description="Read Unit 1 and answer questions 1 to 5 in your notebook.", assigned_date=date.today(),
                    due_date=date.today() + timedelta(days=7), status="published",
                ))
                bump("assignments")
            cycle = ["ENG", "MAT", "SCI", "URD"]
            teaching_periods = [periods[n] for n in (1, 2, 3, 5, 6)]
            for day in range(1, 6):  # Monday to Friday
                for k, period in enumerate(teaching_periods):
                    code = cycle[(day + k) % len(cycle)]
                    exists = db.scalar(select(TimetableSlot.id).where(
                        TimetableSlot.academic_year_id == year.id, TimetableSlot.section_id == section.id,
                        TimetableSlot.day_of_week == day, TimetableSlot.period_id == period.id))
                    if exists is None:
                        db.add(TimetableSlot(
                            academic_year_id=year.id, section_id=section.id, subject_id=subjects[code].id,
                            teacher_id=teachers[code], day_of_week=day, period_id=period.id))
                        bump("timetable_slots")
    db.flush()
    return created


def main() -> None:
    if settings.app_env.lower() == "production":
        sys.exit("Refusing to load sample data when APP_ENV=production")
    try:
        with SessionLocal() as db:
            result = run(db)
            db.commit()
    except RuntimeError as exc:
        sys.exit(str(exc))
    print("seed_ops done. Created:", result or "nothing (already seeded)")


if __name__ == "__main__":
    main()
