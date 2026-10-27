"""FastAPI entry point. Run from backend/:  uvicorn app.main:app --reload

Shared file: only ever ADD one include_router line per module, keep the lists alphabetical
(docs/INTEGRATION_GUIDE.md section 3).
"""
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.db_models  # noqa: F401  (registers all models)
from app.core.config import settings
from app.core.errors import register_error_handlers

# --- member 1 routers (TEMPORARY stub: replace with Faizan's auth router) ---
from app.modules.auth_stub.router import router as auth_stub_router

# --- member 2 routers ---
from app.modules.announcements.router import router as announcements_router
from app.modules.complaints.router import router as complaints_router
from app.modules.exams.router import router as exams_router
from app.modules.fees.router import router as fees_router
from app.modules.homework.router import router as homework_router
from app.modules.lookups.router import router as lookups_router
from app.modules.notifications.router import router as notifications_router
from app.modules.school_calendar.router import router as calendar_router
from app.modules.timetable.router import router as timetable_router

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Trends High School - School Management API",
        version="0.1.0",
        description="Member 2 modules: homework, exams/results, fees, timetable, calendar, announcements, notifications, complaints.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_error_handlers(app)

    api = APIRouter(prefix=API_PREFIX)
    api.include_router(auth_stub_router)
    api.include_router(announcements_router)
    api.include_router(calendar_router)
    api.include_router(complaints_router)
    api.include_router(exams_router)
    api.include_router(fees_router)
    api.include_router(homework_router)
    api.include_router(lookups_router)
    api.include_router(notifications_router)
    api.include_router(timetable_router)
    app.include_router(api)

    @app.get("/health", tags=["System"])
    def health():
        return {"status": "ok"}

    return app


app = create_app()
