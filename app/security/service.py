import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import SessionLocal
from app.security.models import Device


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def register_device(name: str) -> tuple[Device, str]:
    token = secrets.token_urlsafe(32)
    with SessionLocal() as db:
        device = Device(name=name, token_hash=hash_token(token))
        db.add(device)
        db.commit()
        db.refresh(device)
        db.expunge(device)
        return device, token


def authenticate_device(token: str) -> Device | None:
    with SessionLocal() as db:
        device = db.scalar(
            select(Device).where(
                Device.token_hash == hash_token(token), Device.revoked_at.is_(None)
            )
        )
        if device is None:
            return None
        device.last_seen_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(device)
        db.expunge(device)
        return device


def list_devices() -> list[Device]:
    with SessionLocal() as db:
        items = list(db.scalars(select(Device).order_by(Device.created_at.desc())))
        for item in items:
            db.expunge(item)
        return items


def revoke_device(device_id: int) -> bool:
    with SessionLocal() as db:
        item = db.get(Device, device_id)
        if item is None or item.revoked_at is not None:
            return False
        item.revoked_at = datetime.now(timezone.utc)
        db.commit()
        return True
