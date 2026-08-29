from sqlalchemy import desc, select

from app.conversation.models import Conversation, Message, utcnow
from app.database import SessionLocal


def create_conversation(user_id: str, title: str | None = None) -> Conversation:
    with SessionLocal() as db:
        item = Conversation(user_id=user_id, title=title)
        db.add(item)
        db.commit()
        db.refresh(item)
        db.expunge(item)
        return item


def get_conversation(conversation_id: int, user_id: str) -> Conversation | None:
    with SessionLocal() as db:
        item = db.scalar(
            select(Conversation).where(
                Conversation.id == conversation_id, Conversation.user_id == user_id
            )
        )
        if item:
            db.expunge(item)
        return item


def list_conversations(user_id: str, limit: int = 50) -> list[Conversation]:
    with SessionLocal() as db:
        items = list(
            db.scalars(
                select(Conversation)
                .where(Conversation.user_id == user_id)
                .order_by(desc(Conversation.updated_at))
                .limit(limit)
            )
        )
        for item in items:
            db.expunge(item)
        return items


def add_message(conversation_id: int, role: str, content: str) -> Message:
    with SessionLocal() as db:
        item = Message(conversation_id=conversation_id, role=role, content=content)
        conversation = db.get(Conversation, conversation_id)
        if conversation is None:
            raise ValueError("Conversation not found")
        conversation.updated_at = utcnow()
        db.add(item)
        db.commit()
        db.refresh(item)
        db.expunge(item)
        return item


def recent_messages(conversation_id: int, limit: int = 20) -> list[Message]:
    with SessionLocal() as db:
        items = list(
            db.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(desc(Message.created_at), desc(Message.id))
                .limit(limit)
            )
        )
        items.reverse()
        for item in items:
            db.expunge(item)
        return items
