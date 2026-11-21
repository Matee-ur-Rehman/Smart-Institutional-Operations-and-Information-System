"""
Shared foundation tables (DATABASE_SCHEMA.md section 2): users, refresh_tokens, academic_years, classes, sections,
subjects, teachers, students, parents, student_parents, teacher_assignments.
Migration 0001 created the minimum columns; 0003 adds the account-security and profile columns used here.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, SmallInteger, String,
    UniqueConstraint, Uuid, text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, Timestamps, UUIDPk, in_check

ROLES = ("admin", "teacher", "student", "parent")


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint(in_check("role", ROLES), name="role"),)

    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    login_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_login_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))


class RefreshToken(UUIDPk, Base):
    """Server-side record of issued refresh tokens (sha256 of the token) so logout/rotation really invalidates them."""
    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("now()"))


class AcademicYear(UUIDPk, Base):
    __tablename__ = "academic_years"
    __table_args__ = (
        Index("uq_academic_years_current", "is_current", unique=True, postgresql_where=text("is_current")),
    )

    name: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))


class SchoolClass(UUIDPk, Base):
    __tablename__ = "classes"

    name: Mapped[str] = mapped_column(String(50), nullable=False)
    grade_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class Section(UUIDPk, Base):
    __tablename__ = "sections"
    __table_args__ = (UniqueConstraint("class_id", "name"),)

    class_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("classes.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(10), nullable=False)
    class_teacher_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("teachers.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class Subject(UUIDPk, Base):
    __tablename__ = "subjects"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class Teacher(UUIDPk, Base):
    __tablename__ = "teachers"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    employee_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    qualification: Mapped[str | None] = mapped_column(String(150))
    joining_date: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class Student(UUIDPk, Base):
    __tablename__ = "students"
    __table_args__ = (CheckConstraint("gender IS NULL OR gender IN ('male', 'female', 'other')", name="gender"),)

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), unique=True)
    roll_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sections.id"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(10))
    admission_date: Mapped[date | None] = mapped_column(Date)
    address: Mapped[str | None] = mapped_column(String(300))


class Parent(UUIDPk, Base):
    __tablename__ = "parents"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    cnic: Mapped[str | None] = mapped_column(String(15))
    address: Mapped[str | None] = mapped_column(String(300))
    occupation: Mapped[str | None] = mapped_column(String(100))


class StudentParent(Base):
    __tablename__ = "student_parents"

    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id"), primary_key=True)
    parent_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parents.id"), primary_key=True)
    relation: Mapped[str | None] = mapped_column(String(20))


class TeacherAssignment(UUIDPk, Base):
    """Authority for "may this teacher touch this section/subject"."""
    __tablename__ = "teacher_assignments"
    __table_args__ = (UniqueConstraint("section_id", "subject_id", "academic_year_id"),)

    teacher_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("teachers.id"), nullable=False)
    section_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sections.id"), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    academic_year_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("academic_years.id"), nullable=False)
