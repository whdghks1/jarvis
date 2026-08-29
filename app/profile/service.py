from sqlalchemy import select

from app.database import SessionLocal
from app.profile.models import UserProfile


def get_profile(user_id: str) -> UserProfile | None:
    with SessionLocal() as db:
        item = db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
        if item:
            db.expunge(item)
        return item


def upsert_profile(user_id: str, **values: str | None) -> UserProfile:
    with SessionLocal() as db:
        item = db.get(UserProfile, user_id)
        if item is None:
            item = UserProfile(user_id=user_id)
            db.add(item)
        for key, value in values.items():
            if value is not None:
                setattr(item, key, value)
        db.commit()
        db.refresh(item)
        db.expunge(item)
        return item
