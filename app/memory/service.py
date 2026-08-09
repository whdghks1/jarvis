from sqlalchemy import desc, or_, select

from app.database import SessionLocal
from app.memory.models import Memory


def save_memory(
    user_id: str,
    content: str,
    memory_type: str = "fact",
    category: str = "general",
    importance: float = 0.5,
) -> Memory:
    with SessionLocal() as db:
        memory = Memory(
            user_id=user_id,
            content=content.strip(),
            type=memory_type,
            category=category,
            importance=max(0.0, min(1.0, importance)),
        )
        db.add(memory)
        db.commit()
        db.refresh(memory)
        db.expunge(memory)
        return memory


def search_memories(user_id: str, query: str, limit: int = 8) -> list[Memory]:
    with SessionLocal() as db:
        words = [w.strip() for w in query.split() if len(w.strip()) >= 2]

        stmt = select(Memory).where(Memory.user_id == user_id)

        if words:
            stmt = stmt.where(
                or_(*[Memory.content.ilike(f"%{word}%") for word in words])
            )

        stmt = stmt.order_by(desc(Memory.importance), desc(Memory.created_at)).limit(limit)
        items = list(db.scalars(stmt).all())

        for item in items:
            db.expunge(item)
        return items


def recent_memories(user_id: str, limit: int = 10) -> list[Memory]:
    with SessionLocal() as db:
        stmt = (
            select(Memory)
            .where(Memory.user_id == user_id)
            .order_by(desc(Memory.importance), desc(Memory.created_at))
            .limit(limit)
        )
        items = list(db.scalars(stmt).all())
        for item in items:
            db.expunge(item)
        return items
