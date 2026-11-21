"""
Attendance + leave demo data (Member 1 modules).

Run AFTER `python -m seeds.seed_core` (and `seed_ops`, which creates the holiday events it respects):
    python -m seeds.seed_attendance

* Idempotent: attendance is skipped for any (student, date) that already has a row; leave requests are looked
  up by (student, from_date, reason).
* Covers the last 35 days (Mon-Sat, skipping holiday events). Each student has a fixed "reliability" so the same
  few students show low attendance every time. Today is left UNMARKED for 2 sections so the demo dashboard has
  something to show. All data is FAKE.
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.common.scope import audience_user_ids_for_section
from app.common.timeutil import school_now, school_today
from app.core.database import SessionLocal
from app.modules.attendance.models import Attendance
from app.modules.attendance.service import is_holiday, is_school_day
from app.modules.foundation.models import Section, Student, Teacher, TeacherAssignment, User
from app.modules.leave.models import LeaveRequest
from app.modules.notifications.service import notify_users

DAYS = 35
LEAVE_REASONS = [
    ("sick", "Fever and sore throat, doctor advised rest."),
    ("family", "Attending a family wedding out of town."),
    ("sick", "Dental procedure and recovery."),
    ("other", "Visiting grandparents, will return on Monday."),
    ("family", "Family bereavement."),
    ("sick", "Seasonal flu, medical certificate available."),
]


def _marker(db: Session, section_id, admin: User) -> User:
    uid = db.scalar(select(Teacher.user_id).join(TeacherAssignment, TeacherAssignment.teacher_id == Teacher.id)
                    .where(TeacherAssignment.section_id == section_id).limit(1))
    return db.get(User, uid) if uid else admin


def seed_attendance(db: Session) -> dict:
    admin = db.scalar(select(User).where(User.role == "admin"))
    if admin is None:
        raise SystemExit("Run `python -m seeds.seed_core` first")
    today = school_today()
    sections = list(db.scalars(select(Section).order_by(Section.id)))
    unmarked_today = {s.id for s in sections[:2]}
    created = 0
    for sec in sections:
        marker = _marker(db, sec.id, admin)
        students = list(db.scalars(select(Student).where(Student.section_id == sec.id, Student.is_active).order_by(Student.roll_no)))
        done = {(a.student_id, a.attendance_date) for a in db.scalars(select(Attendance).where(Attendance.section_id == sec.id))}
        for back in range(DAYS, -1, -1):
            d = today - timedelta(days=back)
            if not is_school_day(d) or is_holiday(db, d, sec.id) or (d == today and sec.id in unmarked_today):
                continue
            for st in students:
                if (st.id, d) in done:
                    continue
                rng = random.Random(f"att-{st.roll_no}-{d.isoformat()}")
                reliability = 0.97 - (hash_bucket(st.roll_no) % 7) * 0.035     # 0.97 .. 0.76
                x = rng.random()
                status = "present" if x < reliability else ("late" if x < reliability + 0.04 else "absent")
                db.add(Attendance(student_id=st.id, section_id=sec.id, attendance_date=d, status=status,
                                  remarks="Arrived after assembly" if status == "late" else None, marked_by=marker.id))
                created += 1
    db.flush()
    return {"attendance_rows": created}


def hash_bucket(key: str) -> int:
    return sum(ord(c) * (i + 1) for i, c in enumerate(key))


def seed_leave(db: Session) -> dict:
    admin = db.scalar(select(User).where(User.role == "admin"))
    today = school_today()
    students = list(db.scalars(select(Student).where(Student.is_active).order_by(Student.roll_no)))
    created = 0
    plan = [("pending", 2, 2), ("pending", 5, 1), ("approved", -9, 3), ("approved", -20, 2), ("rejected", -14, 1), ("pending", 8, 3)]
    for i, (status, offset, days) in enumerate(plan):
        st = students[(i * 7) % len(students)]
        kind, reason = LEAVE_REASONS[i % len(LEAVE_REASONS)]
        start = today + timedelta(days=offset)
        parent_uid = next(iter(audience_user_ids_for_section(db, st.section_id, include_parents=True,
                                                              include_students=False)), None)
        if parent_uid is None:
            continue
        if db.scalar(select(LeaveRequest.id).where(LeaveRequest.student_id == st.id, LeaveRequest.from_date == start,
                                                    LeaveRequest.reason == reason)):
            continue
        lr = LeaveRequest(student_id=st.id, applied_by=parent_uid, from_date=start, to_date=start + timedelta(days=days - 1),
                          leave_type=kind, reason=reason, status=status)
        if status != "pending":
            lr.decided_by, lr.decided_at = admin.id, school_now()
            lr.decision_note = "Approved." if status == "approved" else "Please apply with a medical note."
        db.add(lr)
        db.flush()
        if status == "pending":
            notify_users(db, [admin.id], "New leave request", f"{st.full_name}: {lr.from_date:%d %b} to {lr.to_date:%d %b %Y}",
                         "leave", "leave", lr.id)
        created += 1
    return {"leave_requests": created}


def run(db: Session | None = None) -> dict:
    own = db is None
    db = db or SessionLocal()
    try:
        stats = {**seed_attendance(db), **seed_leave(db)}
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
