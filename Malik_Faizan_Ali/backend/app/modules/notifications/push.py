"""
Firebase Cloud Messaging sender. OFF unless FCM_ENABLED=true AND FCM_CREDENTIALS_FILE exists.
The in-app inbox never depends on this file. Real delivery cannot be verified until real Firebase
credentials exist (see README "Push notifications"); the logic here is unit-tested with a fake sender.
"""
import logging
import os
import threading
import uuid

from sqlalchemy import event, select, update
from sqlalchemy.orm import Session

from app.core.config import settings

log = logging.getLogger("app.push")
_firebase_app = None
_lock = threading.Lock()


def fcm_ready() -> bool:
    return bool(settings.FCM_ENABLED and settings.FCM_CREDENTIALS_FILE and os.path.isfile(settings.FCM_CREDENTIALS_FILE))


def initial_push_status() -> str:
    return "queued" if fcm_ready() else "disabled"


def _send_one(token: str, title: str, body: str, data: dict[str, str]) -> None:
    """Send one message through firebase-admin. Raises on failure (caller records 'failed')."""
    global _firebase_app
    import firebase_admin  # imported lazily: optional dependency
    from firebase_admin import credentials, messaging

    with _lock:
        if _firebase_app is None:
            _firebase_app = firebase_admin.initialize_app(credentials.Certificate(settings.FCM_CREDENTIALS_FILE))
    messaging.send(messaging.Message(token=token, notification=messaging.Notification(title=title, body=body), data=data))


def send_pending(notification_ids: list[uuid.UUID]) -> None:
    """Deliver queued notifications to their users' registered devices. Never raises."""
    from app.core.database import SessionLocal
    from app.modules.notifications.models import DeviceToken, Notification

    try:
        with SessionLocal() as db:
            for n in db.scalars(select(Notification).where(Notification.id.in_(notification_ids))):
                tokens = list(db.scalars(select(DeviceToken.token).where(DeviceToken.user_id == n.user_id)))
                status = "failed"
                if tokens:
                    ok = 0
                    for t in tokens:
                        try:
                            _send_one(t, n.title, n.body, {"type": n.type, "reference_id": str(n.reference_id or ""),
                                                           "reference_type": n.reference_type or ""})
                            ok += 1
                        except Exception:  # noqa: BLE001 - one bad token must not stop the rest
                            log.warning("FCM send failed for a token of user %s", n.user_id, exc_info=True)
                    status = "sent" if ok else "failed"
                db.execute(update(Notification).where(Notification.id == n.id).values(push_status=status))
            db.commit()
    except Exception:  # noqa: BLE001
        log.exception("Push dispatch failed")


def _after_commit(session: Session) -> None:
    ids = session.info.pop("pending_push", None)
    if ids and fcm_ready():
        threading.Thread(target=send_pending, args=(ids,), daemon=True).start()


def _after_rollback(session: Session) -> None:
    session.info.pop("pending_push", None)


def register_hooks() -> None:
    if not event.contains(Session, "after_commit", _after_commit):
        event.listen(Session, "after_commit", _after_commit)
        event.listen(Session, "after_soft_rollback", lambda s, _t: _after_rollback(s))
