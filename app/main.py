import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from agents import Runner
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.agent.context import JarvisContext
from app.agent.jarvis import jarvis
from app.config import get_settings
from app.conversation.service import (
    add_message,
    create_conversation,
    get_conversation,
    list_conversations,
    recent_messages,
)
from app.database import SessionLocal, create_schema
from app.memory.service import delete_memory, recent_memories, save_memory, update_memory
from app.profile.service import get_profile, upsert_profile
from app.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ConversationOut,
    MemoryCreate,
    MemoryOut,
    MemoryUpdate,
    MessageOut,
    ProfileOut,
    ProfileUpdate,
)

settings = get_settings()
owner_id = settings.owner_id
static_dir = Path(__file__).parent / "static"
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("jarvis")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.auto_create_tables:
        create_schema()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "ok", "version": settings.app_version}


@app.get("/ready")
def ready():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception as exc:
        logger.exception("Database readiness check failed")
        raise HTTPException(status_code=503, detail="Database is unavailable") from exc


@app.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest):
    conversation = None
    if body.conversation_id is not None:
        conversation = get_conversation(body.conversation_id, owner_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = create_conversation(
            owner_id, title=body.message[:80]
        )

    history = recent_messages(
        conversation.id, limit=settings.conversation_history_limit
    )
    agent_input = [
        {"role": item.role, "content": item.content}
        for item in history
        if item.role in {"user", "assistant"}
    ]
    profile = get_profile(owner_id)
    if profile is not None:
        agent_input.insert(
            0,
            {
                "role": "system",
                "content": (
                    "Known user profile: "
                    f"display_name={profile.display_name or 'unknown'}, "
                    f"timezone={profile.timezone}, locale={profile.locale}, "
                    f"preferred_language={profile.preferred_language}."
                ),
            },
        )
    agent_input.append({"role": "user", "content": body.message})
    add_message(conversation.id, "user", body.message)

    try:
        result = await Runner.run(
            jarvis,
            agent_input,
            context=JarvisContext(user_id=owner_id),
        )
        reply = str(result.final_output)
        add_message(conversation.id, "assistant", reply)
        return ChatResponse(reply=reply, conversation_id=conversation.id)
    except Exception as exc:
        logger.exception("Agent run failed", extra={"conversation_id": conversation.id})
        raise HTTPException(
            status_code=502, detail="The assistant could not complete the request"
        ) from exc


@app.post("/conversations", response_model=ConversationOut, status_code=201)
def conversations_create(body: ConversationCreate):
    return create_conversation(owner_id, body.title)


@app.get("/conversations", response_model=list[ConversationOut])
def conversations_list(
    limit: int = Query(default=50, ge=1, le=100),
):
    return list_conversations(owner_id, limit)


@app.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def conversation_messages(
    conversation_id: int,
    limit: int = Query(default=100, ge=1, le=200),
):
    if get_conversation(conversation_id, owner_id) is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return recent_messages(conversation_id, limit)


@app.get("/memories", response_model=list[MemoryOut])
def memories(limit: int = Query(default=10, ge=1, le=100)):
    return recent_memories(owner_id, limit)


@app.post("/memories", response_model=MemoryOut, status_code=201)
def create_memory(body: MemoryCreate):
    return save_memory(
        user_id=owner_id,
        content=body.content,
        memory_type=body.type,
        category=body.category,
        importance=body.importance,
        normalized_key=body.normalized_key,
    )


@app.patch("/memories/{memory_id}", response_model=MemoryOut)
def memory_update(
    memory_id: int,
    body: MemoryUpdate,
):
    item = update_memory(owner_id, memory_id, **body.model_dump(exclude_unset=True))
    if item is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return item


@app.delete("/memories/{memory_id}", status_code=204)
def memory_delete(
    memory_id: int,
):
    if not delete_memory(owner_id, memory_id):
        raise HTTPException(status_code=404, detail="Memory not found")


@app.get("/profile", response_model=ProfileOut)
def profile_get():
    item = get_profile(owner_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return item


@app.put("/profile", response_model=ProfileOut)
def profile_put(body: ProfileUpdate):
    return upsert_profile(owner_id, **body.model_dump())


@app.get("/", include_in_schema=False)
def web_app():
    return FileResponse(static_dir / "index.html")


app.mount("/static", StaticFiles(directory=static_dir), name="static")
