"""Optional Firebase Cloud Messaging sender.

UNTESTED: it needs a real Firebase project, which does not exist yet. With FCM_ENABLED=false
(the default) nothing in this file runs and notifications still appear in the in-app inbox.
To enable later see backend/README_MEMBER2.md ("Turning on push notifications").
"""
import logging
import os

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.modules.notifications.models import DeviceToken, Notification

log = logging.getLogger("app.push")
_firebase_ready = False


def _init_firebase() -> bool:
    global _firebase_ready
    if _firebase_ready:
        return True
    if not settings.fcm_credentials_file or not os.path.isfile(settings.fcm_credentials_file):
        log.warning("FCM_ENABLED is true but FCM_CREDENTIALS_FILE is missing; push is skipped")
        return False
    try:
        import firebase_admin
        from firebase_admin import credentials
    except ImportError:
        log.warning("firebase-admin is not installed; push is skipped")
        return False
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(settings.fcm_credentials_file))
    _firebase_ready = True
    return True


def dispatch_queued_pushes(limit: int = 500) -> None:
    """Background task: send pushes for notifications marked 'queued'. Never raises."""
    if not settings.fcm_enabled or not _init_firebase():
        return
    try:
        from firebase_admin import messaging
        with SessionLocal() as db:
            queued = list(db.scalars(select(Notification).where(Notification.push_status == "queued").limit(limit)))
            for note in queued:
                tokens = list(db.scalars(select(DeviceToken.token).where(DeviceToken.user_id == note.user_id)))
                if not tokens:
                    note.push_status = "not_sent"
                    continue
                ok = False
                for token in tokens:
                    try:
                        messaging.send(
                            messaging.Message(
                                token=token,
                                notification=messaging.Notification(title=note.title, body=note.body[:200]),
                                data={"type": note.type, "notification_id": str(note.id)},
                            )
                        )
                        ok = True
                    except Exception:  # one bad token must not stop the others
                        log.exception("FCM send failed for one token")
                note.push_status = "sent" if ok else "failed"
            db.commit()
    except Exception:
        log.exception("Push dispatch failed")
