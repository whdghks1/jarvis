import logging
import hmac
import json
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from agents import Runner
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.agent.context import JarvisContext
from app.agent.jarvis import jarvis
from app.action.service import create_action, list_actions, transition_action
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
from app.security.service import (
    authenticate_device,
    list_devices,
    register_device,
    revoke_device,
)
from app.schemas import (
    ChatRequest,
    ChatResponse,
    ActionCreate,
    ActionOut,
    ActionResult,
    ConversationCreate,
    ConversationOut,
    MemoryCreate,
    MemoryOut,
    MemoryUpdate,
    MessageOut,
    ProfileOut,
    ProfileUpdate,
    DeviceOut,
    DeviceRegistration,
    DeviceTokenOut,
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
    if settings.auth_required:
        logger.warning("JARVIS device pairing code: %s", settings.pairing_code)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

public_paths = {"/", "/health", "/ready", "/device-registration", "/docs", "/openapi.json", "/redoc"}


@app.middleware("http")
async def device_authentication(request: Request, call_next):
    request.state.device_id = None
    if (
        not settings.auth_required
        or request.url.path in public_paths
        or request.url.path.startswith("/static/")
    ):
        return await call_next(request)
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return JSONResponse(status_code=401, content={"detail": "Device authentication required"})
    device = authenticate_device(token)
    if device is None:
        return JSONResponse(status_code=401, content={"detail": "Invalid or revoked device token"})
    request.state.device_id = device.id
    return await call_next(request)


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


@app.post("/device-registration", response_model=DeviceTokenOut, status_code=201)
def device_registration(body: DeviceRegistration):
    if not hmac.compare_digest(body.pairing_code, settings.pairing_code):
        raise HTTPException(status_code=403, detail="Invalid pairing code")
    device, token = register_device(body.name)
    return DeviceTokenOut(device_id=device.id, access_token=token)


@app.get("/devices", response_model=list[DeviceOut])
def devices_list():
    return list_devices()


@app.delete("/devices/{device_id}", status_code=204)
def device_revoke(device_id: int):
    if not revoke_device(device_id):
        raise HTTPException(status_code=404, detail="Active device not found")


@app.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest):
    conversation, agent_input = _prepare_chat(body)

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


def _prepare_chat(body: ChatRequest):
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
    return conversation, agent_input


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/chat/stream")
async def chat_stream(body: ChatRequest):
    conversation, agent_input = _prepare_chat(body)

    async def generate():
        result = None
        try:
            yield _sse("conversation", {"conversation_id": conversation.id})
            result = Runner.run_streamed(
                jarvis,
                agent_input,
                context=JarvisContext(user_id=owner_id),
            )
            async for event in result.stream_events():
                if event.type != "raw_response_event":
                    continue
                data = event.data
                if getattr(data, "type", None) == "response.output_text.delta":
                    yield _sse("delta", {"text": data.delta})
            if result.run_loop_exception:
                raise result.run_loop_exception
            reply = str(result.final_output)
            add_message(conversation.id, "assistant", reply)
            yield _sse(
                "done", {"reply": reply, "conversation_id": conversation.id}
            )
        except Exception:
            logger.exception(
                "Streamed agent run failed",
                extra={"conversation_id": conversation.id},
            )
            yield _sse("error", {"detail": "The assistant could not complete the request"})
        finally:
            if result is not None and not result.is_complete:
                result.cancel()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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


@app.post("/actions", response_model=ActionOut, status_code=201)
def action_create(body: ActionCreate, request: Request):
    try:
        return create_action(
            action_type=body.action_type,
            title=body.title,
            description=body.description,
            payload=body.payload,
            device_id=request.state.device_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/actions", response_model=list[ActionOut])
def actions_list(
    status: str | None = Query(default=None, max_length=30),
    limit: int = Query(default=50, ge=1, le=100),
):
    return list_actions(status, limit)


def _transition_or_error(
    action_id: int,
    event: str,
    target_status: str,
    device_id: int | None,
    result: dict | None = None,
):
    try:
        item = transition_action(
            action_id, event, target_status, device_id, result=result
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if item is None:
        raise HTTPException(status_code=404, detail="Action not found")
    return item


@app.post("/actions/{action_id}/approve", response_model=ActionOut)
def action_approve(action_id: int, request: Request):
    return _transition_or_error(
        action_id, "approved", "approved", request.state.device_id
    )


@app.post("/actions/{action_id}/cancel", response_model=ActionOut)
def action_cancel(action_id: int, request: Request):
    return _transition_or_error(
        action_id, "cancelled", "cancelled", request.state.device_id
    )


@app.post("/actions/{action_id}/result", response_model=ActionOut)
def action_result(action_id: int, body: ActionResult, request: Request):
    status = "completed" if body.success else "failed"
    return _transition_or_error(
        action_id,
        status,
        status,
        request.state.device_id,
        result={"success": body.success, "detail": body.detail},
    )


@app.get("/", include_in_schema=False)
def web_app():
    return FileResponse(static_dir / "index.html")


app.mount("/static", StaticFiles(directory=static_dir), name="static")
