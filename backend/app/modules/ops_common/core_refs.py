"""Single place where Member 2's code imports Member 1's models.

Today these come from the temporary stub (app/core/stub_models.py). When Faizan's real models are
merged, change ONLY this import block to point at his modules; nothing else in Member 2's code
needs to change as long as the class names below keep working.
"""
from app.core.stub_models import (  # noqa: F401
    AcademicYear,
    Parent,
    SchoolClass,
    Section,
    Student,
    StudentParent,
    Subject,
    Teacher,
    TeacherAssignment,
    User,
)
