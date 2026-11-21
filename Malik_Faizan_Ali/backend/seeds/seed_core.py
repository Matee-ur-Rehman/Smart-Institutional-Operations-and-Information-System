"""
Foundation seed (DATABASE_SCHEMA.md section 2): academic year, classes, sections, subjects, teachers + teacher_assignments,
students, parents, parent-child links and user accounts for every role. Run it before seeds/seed_ops.py.

Idempotent: every row is looked up by a natural key (login_id, roll_no, code, name, ...) before insert.
All people and phone numbers are FAKE. Passwords come from env (never stored in the repo):
  SEED_ADMIN_PASSWORD, SEED_USER_PASSWORD  (dev defaults are used only when APP_ENV != production).
Logins: admin, teacher1..10, student1..48, parent1..40.
"""
from __future__ import annotations

import sys
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.modules.foundation.models import (
    AcademicYear, Parent, SchoolClass, Section, Student, StudentParent, Subject, Teacher, TeacherAssignment, User,
)

DEV_ADMIN_PASSWORD = "Admin@12345"
DEV_USER_PASSWORD = "School@12345"

CLASSES = [("Class 6", 6), ("Class 7", 7), ("Class 8", 8), ("Class 9", 9), ("Class 10", 10)]

# Section order matters: students are numbered student1.. in this order (student1 is in 8-A).
SECTIONS = [("Class 8", "A"), ("Class 6", "A"), ("Class 7", "A"), ("Class 8", "B"), ("Class 9", "A"), ("Class 10", "A")]

SUBJECTS = {
    "ENG": "English", "URD": "Urdu", "MATH": "Mathematics", "SCI": "General Science", "PHY": "Physics",
    "CHEM": "Chemistry", "BIO": "Biology", "CS": "Computer Science", "ISL": "Islamiyat", "PKS": "Pakistan Studies",
}
JUNIOR_SUBJECTS = ["ENG", "URD", "MATH", "SCI", "CS", "ISL", "PKS"]            # classes 6-7
SENIOR_SUBJECTS = ["ENG", "URD", "MATH", "PHY", "CHEM", "BIO", "CS", "ISL", "PKS"]  # classes 8-10

# Periods per week for each subject (used by seed_ops' timetable allocator): junior / senior.
WEEKLY_PERIODS_JUNIOR = {"MATH": 6, "ENG": 6, "URD": 5, "SCI": 5, "CS": 4, "ISL": 4, "PKS": 4}
WEEKLY_PERIODS_SENIOR = {"MATH": 6, "ENG": 6, "URD": 5, "PHY": 4, "CHEM": 4, "BIO": 4, "CS": 3, "ISL": 3, "PKS": 3}

# (teacher no, full name, speciality)
TEACHERS = [
    (1, "Muhammad Imran Qureshi", "Mathematics"),
    (2, "Sadia Naveed", "Mathematics & Computer Science"),
    (3, "Ayesha Siddiqui", "English"),
    (4, "Rizwan Ahmed Khan", "English"),
    (5, "Farah Naz", "Urdu"),
    (6, "Hafiz Bilal Hussain", "Urdu & Islamiyat"),
    (7, "Tariq Mehmood Awan", "Pakistan Studies & Science"),
    (8, "Dr. Saira Batool", "Physics"),
    (9, "Kashif Raza", "Chemistry"),
    (10, "Nimra Shahid", "Biology"),
]

# (section label, subject code) -> teacher no.  Weekly loads: T1 24, T2 32, T3 18+.. all < 42 periods.
_ASSIGN_RULES = {
    "MATH": {"8-A": 1, "8-B": 1, "6-A": 1, "7-A": 1, "9-A": 2, "10-A": 2},
    "CS": {s: 2 for s in ("6-A", "7-A", "8-A", "8-B", "9-A", "10-A")},
    "ENG": {"6-A": 3, "7-A": 3, "8-A": 3, "8-B": 4, "9-A": 4, "10-A": 4},
    "URD": {"6-A": 5, "7-A": 5, "8-A": 5, "8-B": 5, "9-A": 6, "10-A": 6},
    "ISL": {s: 6 for s in ("6-A", "7-A", "8-A", "8-B", "9-A", "10-A")},
    "PKS": {s: 7 for s in ("6-A", "7-A", "8-A", "8-B", "9-A", "10-A")},
    "SCI": {"6-A": 7, "7-A": 7},
    "PHY": {s: 8 for s in ("8-A", "8-B", "9-A", "10-A")},
    "CHEM": {s: 9 for s in ("8-A", "8-B", "9-A", "10-A")},
    "BIO": {s: 10 for s in ("8-A", "8-B", "9-A", "10-A")},
}
TEACHER_OF: dict[tuple[str, str], int] = {(sec, sub): t for sub, m in _ASSIGN_RULES.items() for sec, t in m.items()}
CLASS_TEACHER = {"6-A": 3, "7-A": 5, "8-A": 1, "8-B": 4, "9-A": 2, "10-A": 8}

BOYS = ["Ahmed", "Ali", "Hamza", "Usman", "Bilal", "Hassan", "Zain", "Talha", "Saad", "Daniyal", "Faizan", "Ibrahim",
        "Abdullah", "Umar", "Shahzaib", "Huzaifa", "Arslan", "Haris", "Mubashir", "Salman", "Rayyan", "Taimoor"]
GIRLS = ["Fatima", "Ayesha", "Zainab", "Maryam", "Hira", "Sana", "Noor", "Laiba", "Areeba", "Iqra", "Khadija", "Amna",
         "Mahnoor", "Eman", "Hoorain", "Alishba", "Rabia", "Sidra", "Anum", "Minahil", "Dua", "Aroosa"]
SURNAMES = ["Khan", "Malik", "Awan", "Butt", "Raja", "Qureshi", "Mirza", "Chaudhry", "Abbasi", "Satti", "Janjua",
            "Gillani", "Niazi", "Sheikh", "Baig", "Rana", "Cheema", "Yousaf", "Javed", "Hashmi", "Zafar", "Bukhari",
            "Tanoli", "Kayani", "Mughal", "Dar", "Anwar", "Siddiqui", "Farooq", "Aslam", "Rehman", "Iqbal", "Hussain",
            "Tariq", "Shah", "Naqvi", "Ghani", "Memon", "Lodhi", "Pervaiz", "Saleem", "Nawaz", "Sultan", "Rasheed",
            "Zahid", "Mansoor", "Akram", "Haider"]
FATHER_FIRST = ["Muhammad", "Abdul", "Tahir", "Nadeem", "Shahid", "Javed", "Khalid", "Aslam", "Naveed", "Irfan",
                "Zahid", "Sajid", "Waseem", "Rashid", "Majid", "Asif", "Pervez", "Liaqat", "Riaz", "Munir"]
MOTHER_FIRST = ["Shazia", "Nasreen", "Samina", "Rukhsana", "Tahira", "Parveen", "Farzana", "Shaheen", "Robina", "Naheed"]

# Students (1-based index in numbering order) that share a parent with an earlier student (siblings).
SIBLINGS = {9: 1, 26: 2, 18: 3, 34: 4, 19: 10, 42: 5, 35: 27, 43: 36}   # sibling -> older sibling

SCHOOL_SLUG = "TH"


def section_label(class_name: str, sec: str) -> str:
    return f"{class_name.replace('Class ', '')}-{sec}"


def passwords() -> tuple[str, str]:
    admin, user = settings.SEED_ADMIN_PASSWORD, settings.SEED_USER_PASSWORD
    if settings.APP_ENV == "production":
        if not admin or not user:
            sys.exit("Refusing to seed in production without SEED_ADMIN_PASSWORD and SEED_USER_PASSWORD.")
    return admin or DEV_ADMIN_PASSWORD, user or DEV_USER_PASSWORD


def _get_or_create_user(db: Session, login_id: str, role: str, full_name: str, password: str, *, email=None, phone=None) -> User:
    u = db.scalar(select(User).where(User.login_id == login_id))
    if u is None:
        u = User(login_id=login_id, role=role, full_name=full_name, password_hash=hash_password(password),
                 email=email, phone=phone, is_active=True)
        db.add(u)
        db.flush()
    return u


def run(db: Session | None = None) -> dict:
    own = db is None
    db = db or SessionLocal()
    admin_pw, user_pw = passwords()
    stats = {}
    try:
        # --- academic year
        year = db.scalar(select(AcademicYear).where(AcademicYear.name == "2026-2027"))
        if year is None:
            db.execute(AcademicYear.__table__.update().values(is_current=False))
            year = AcademicYear(name="2026-2027", start_date=date(2026, 4, 1), end_date=date(2027, 3, 31), is_current=True)
            db.add(year)
            db.flush()
        elif not db.scalar(select(AcademicYear.id).where(AcademicYear.is_current)):
            year.is_current = True

        # --- classes / sections / subjects
        classes = {}
        for name, grade in CLASSES:
            c = db.scalar(select(SchoolClass).where(SchoolClass.name == name))
            if c is None:
                c = SchoolClass(name=name, grade_level=grade)
                db.add(c)
                db.flush()
            classes[name] = c
        sections: dict[str, Section] = {}
        for cname, sec in SECTIONS:
            s = db.scalar(select(Section).where(Section.class_id == classes[cname].id, Section.name == sec))
            if s is None:
                s = Section(class_id=classes[cname].id, name=sec)
                db.add(s)
                db.flush()
            sections[section_label(cname, sec)] = s
        subjects: dict[str, Subject] = {}
        for code, name in SUBJECTS.items():
            s = db.scalar(select(Subject).where(Subject.code == code))
            if s is None:
                s = Subject(code=code, name=name)
                db.add(s)
                db.flush()
            subjects[code] = s

        # --- admin + teachers
        _get_or_create_user(db, "admin", "admin", "Principal Office (Admin)", admin_pw, email="admin@trends-school.example.com", phone="0300-0000001")
        teachers: dict[int, Teacher] = {}
        for no, name, _spec in TEACHERS:
            u = _get_or_create_user(db, f"teacher{no}", "teacher", name, user_pw, email=f"teacher{no}@trends-school.example.com",
                                    phone=f"0301-10000{no:02d}")
            t = db.scalar(select(Teacher).where(Teacher.user_id == u.id))
            if t is None:
                t = Teacher(user_id=u.id, employee_no=f"TH-T-{no:03d}")
                db.add(t)
                db.flush()
            teachers[no] = t

        # --- teacher assignments + class teachers
        for (sec, code), tno in TEACHER_OF.items():
            exists = db.scalar(select(TeacherAssignment.id).where(
                TeacherAssignment.section_id == sections[sec].id, TeacherAssignment.subject_id == subjects[code].id,
                TeacherAssignment.academic_year_id == year.id))
            if exists is None:
                db.add(TeacherAssignment(teacher_id=teachers[tno].id, section_id=sections[sec].id,
                                         subject_id=subjects[code].id, academic_year_id=year.id))
        for sec, tno in CLASS_TEACHER.items():
            if sections[sec].class_teacher_id is None:
                sections[sec].class_teacher_id = teachers[tno].id
        db.flush()

        # --- students + parents
        n = 0
        parent_of_student: dict[int, Parent] = {}
        parent_no = 0
        for cname, sec in SECTIONS:
            label = section_label(cname, sec)
            for roll in range(1, 9):
                n += 1
                girl = n % 2 == 0
                first = (GIRLS if girl else BOYS)[(n * 7) % 22]
                last = SURNAMES[(n * 5 + 3) % len(SURNAMES)]
                full = f"{first} {last}"
                su = _get_or_create_user(db, f"student{n}", "student", full, user_pw, email=f"student{n}@trends-school.example.com",
                                         phone=None)
                st = db.scalar(select(Student).where(Student.roll_no == f"{SCHOOL_SLUG}-{label.replace('-', '')}-{roll:02d}"))
                if st is None:
                    st = Student(user_id=su.id, roll_no=f"{SCHOOL_SLUG}-{label.replace('-', '')}-{roll:02d}", full_name=full,
                                 section_id=sections[label].id)
                    db.add(st)
                    db.flush()
                # parent
                if n in SIBLINGS:
                    parent = parent_of_student[SIBLINGS[n]]
                    relation = None
                else:
                    parent_no += 1
                    is_mother = parent_no % 7 == 0
                    is_guardian = parent_no % 11 == 0
                    pname = (f"{MOTHER_FIRST[parent_no % 10]} {last}" if is_mother else f"{FATHER_FIRST[parent_no % 20]} {last}")
                    pu = _get_or_create_user(db, f"parent{parent_no}", "parent", pname, user_pw,
                                             email=f"parent{parent_no}@example.com", phone=f"0300-5{parent_no:06d}")
                    parent = db.scalar(select(Parent).where(Parent.user_id == pu.id))
                    if parent is None:
                        parent = Parent(user_id=pu.id)
                        db.add(parent)
                        db.flush()
                    relation = "guardian" if is_guardian else ("mother" if is_mother else "father")
                parent_of_student[n] = parent
                if db.scalar(select(StudentParent.student_id).where(StudentParent.student_id == st.id,
                                                                     StudentParent.parent_id == parent.id)) is None:
                    db.add(StudentParent(student_id=st.id, parent_id=parent.id, relation=relation or "father"))
        db.commit()
        stats = {"classes": len(classes), "sections": len(sections), "subjects": len(subjects), "teachers": len(teachers),
                 "students": n, "parents": parent_no}
        return stats
    finally:
        if own:
            db.close()


if __name__ == "__main__":
    print(run())
