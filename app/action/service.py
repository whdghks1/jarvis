from datetime import datetime, timezone
import re

from sqlalchemy import desc, select

from app.action.models import ActionAuditLog, PendingAction
from app.database import SessionLocal

ALLOWED_ACTION_TYPES = {"calendar.create", "navigation.open", "phone.dial"}


def _validate_payload(action_type: str, payload: dict) -> None:
    if action_type == "phone.dial":
        number = payload.get("phone_number")
        if not isinstance(number, str) or not re.fullmatch(r"[0-9+() -]{3,32}", number):
            raise ValueError("phone.dial requires a valid phone_number")
    elif action_type == "navigation.open":
        destination = payload.get("destination")
        if not isinstance(destination, str) or not 1 <= len(destination.strip()) <= 500:
            raise ValueError("navigation.open requires a destination")
    elif action_type == "calendar.create":
        title = payload.get("title")
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 200:
            raise ValueError("calendar.create requires a title")
        for key in ("start_millis", "end_millis"):
            if key in payload and not isinstance(payload[key], int):
                raise ValueError(f"calendar.create {key} must be an integer")


def create_action(
    action_type: str,
    title: str,
    payload: dict,
    description: str | None = None,
    device_id: int | None = None,
) -> PendingAction:
    if action_type not in ALLOWED_ACTION_TYPES:
        raise ValueError("Unsupported action type")
    _validate_payload(action_type, payload)
    with SessionLocal() as db:
        item = PendingAction(
            action_type=action_type,
            title=title,
            description=description,
            payload=payload,
            requested_by_device_id=device_id,
        )
        db.add(item)
        db.flush()
        db.add(ActionAuditLog(action_id=item.id, event="proposed", device_id=device_id))
        db.commit()
        db.refresh(item)
        db.expunge(item)
        return item


def list_actions(status: str | None = None, limit: int = 50) -> list[PendingAction]:
    with SessionLocal() as db:
        stmt = select(PendingAction)
        if status:
            stmt = stmt.where(PendingAction.status == status)
        items = list(db.scalars(stmt.order_by(desc(PendingAction.created_at)).limit(limit)))
        for item in items:
            db.expunge(item)
        return items


def transition_action(
    action_id: int,
    event: str,
    target_status: str,
    device_id: int | None,
    result: dict | None = None,
) -> PendingAction | None:
    with SessionLocal() as db:
        item = db.get(PendingAction, action_id)
        if item is None:
            return None
        allowed = {
            "approved": {"pending_confirmation"},
            "cancelled": {"pending_confirmation", "approved"},
            "completed": {"approved", "executing"},
            "failed": {"approved", "executing"},
        }
        if item.status not in allowed.get(target_status, set()):
            raise ValueError(f"Cannot transition {item.status} to {target_status}")
        item.status = target_status
        if result is not None:
            item.result = result
        if target_status in {"completed", "failed", "cancelled"}:
            item.completed_at = datetime.now(timezone.utc)
        db.add(ActionAuditLog(action_id=item.id, event=event, device_id=device_id))
        db.commit()
        db.refresh(item)
        db.expunge(item)
        return item
