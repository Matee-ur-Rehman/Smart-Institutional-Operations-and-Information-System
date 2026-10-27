"""TEMPORARY STUB of Member 1's foundation tables (docs/DATABASE_SCHEMA.md section 2).

Written by Member 2 only so that Member 2's modules, migrations, seeds and tests can run before
Faizan's code is merged. DELETE this file when Faizan's real models land, then change the single
import block in app/modules/ops_common/core_refs.py and the import in app/db_models.py.
Only the minimum columns from the schema document exist here.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, SmallInteger, String, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.ops_common.base import TimestampMixin, check_in, uuid_pk


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (check_in("users", "role", ["admin", "teacher", "student", "parent"]),)

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    login_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AcademicYear(Base):
    __tablename__ = "academic_years"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))


class SchoolClass(Base):
    __tablename__ = "classes"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    grade_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), unique=True, nullable=False)
    employee_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class Section(Base):
    __tablename__ = "sections"
    __table_args__ = (UniqueConstraint("class_id", "name"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    class_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("classes.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(10), nullable=False)
    class_teacher_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("teachers.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class Student(Base):
    __tablename__ = "students"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id"), unique=True)
    roll_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    section_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("sections.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))


class Parent(Base):
    __tablename__ = "parents"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), unique=True, nullable=False)
    cnic: Mapped[str | None] = mapped_column(String(15))


class StudentParent(Base):
    __tablename__ = "student_parents"

    student_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("students.id"), primary_key=True)
    parent_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("parents.id"), primary_key=True)
    relation: Mapped[str] = mapped_column(String(20), nullable=False, default="guardian")


class TeacherAssignment(Base):
    __tablename__ = "teacher_assignments"
    __table_args__ = (UniqueConstraint("section_id", "subject_id", "academic_year_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    teacher_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("teachers.id"), nullable=False)
    section_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("sections.id"), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("subjects.id"), nullable=False)
    academic_year_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("academic_years.id"), nullable=False)
