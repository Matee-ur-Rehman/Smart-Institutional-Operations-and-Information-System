"""FastAPI entry point. Every module registers one router here (one line per module, alphabetical)."""
import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import register_error_handlers
from app.modules.announcements.router import router as announcements_router
from app.modules.attendance.router import router as attendance_router
from app.modules.calendar.router import router as calendar_router
from app.modules.complaints.router import router as complaints_router
from app.modules.exams.router import router as exams_router
from app.modules.fees.router import router as fees_router
from app.modules.foundation.academics_router import router as academics_router
from app.modules.foundation.auth_router import router as auth_router
from app.modules.foundation.people_router import router as people_router
from app.modules.foundation.users_router import router as users_router
from app.modules.homework.router import router as homework_router
from app.modules.leave.router import router as leave_router
from app.modules.lookups.router import router as lookups_router
from app.modules.notifications.push import register_hooks
from app.modules.notifications.router import router as notifications_router
from app.modules.reports.router import router as reports_router
from app.modules.timetable.router import router as timetable_router

logging.basicConfig(level=logging.INFO)
API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_: FastAPI):
    register_hooks()
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    if settings.APP_ENV == "production" and settings.JWT_SECRET_KEY.startswith("CHANGE_ME"):
        raise RuntimeError("Refusing to start in production with the placeholder JWT_SECRET_KEY")
    yield


app = FastAPI(
    title="Trends High School — Smart Institutional Operations and Information System",
    description="REST API. Operations modules: homework, exams & results, fees, timetable, calendar, "
                "announcements & notifications, complaints. Foundation (auth, users, people, academics) is in app/modules/foundation.",
    version="0.1.0", lifespan=lifespan,
)
register_error_handlers(app)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

api = APIRouter(prefix=API_PREFIX)
api.include_router(announcements_router)
api.include_router(attendance_router)
api.include_router(academics_router)
api.include_router(auth_router)
api.include_router(calendar_router)
api.include_router(complaints_router)
api.include_router(exams_router)
api.include_router(fees_router)
api.include_router(homework_router)
api.include_router(leave_router)
api.include_router(lookups_router)
api.include_router(notifications_router)
api.include_router(people_router)
api.include_router(reports_router)
api.include_router(timetable_router)
api.include_router(users_router)


@api.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}


app.include_router(api)
