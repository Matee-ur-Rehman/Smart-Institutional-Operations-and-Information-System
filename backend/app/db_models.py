"""Imports every SQLAlchemy model so they are registered on Base.metadata (used by Alembic, the
seed scripts and the tests). Each member keeps their own block; add one line per new model module.
"""
# --- member 1 ---------------------------------------------------------------------------------
# TEMPORARY: replace this line with Faizan's real model imports when they are merged.
import app.core.stub_models  # noqa: F401

# --- member 2 ---------------------------------------------------------------------------------
import app.modules.announcements.models  # noqa: F401
import app.modules.complaints.models  # noqa: F401
import app.modules.exams.models  # noqa: F401
import app.modules.fees.models  # noqa: F401
import app.modules.homework.models  # noqa: F401
import app.modules.notifications.models  # noqa: F401
import app.modules.school_calendar.models  # noqa: F401
import app.modules.timetable.models  # noqa: F401
