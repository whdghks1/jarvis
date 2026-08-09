from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException
from agents import Runner

from app.agent.context import JarvisContext
from app.agent.jarvis import jarvis
from app.database import Base, engine
from app.memory.service import recent_memories
from app.schemas import ChatRequest, ChatResponse, MemoryOut


Base.metadata.create_all(bind=engine)

app = FastAPI(title="JARVIS API", version="0.1.0")


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}


@app.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest):
    try:
        result = await Runner.run(
            jarvis,
            body.message,
            context=JarvisContext(user_id=body.user_id),
        )
        return ChatResponse(reply=str(result.final_output))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/memories/{user_id}", response_model=list[MemoryOut])
def memories(user_id: str):
    items = recent_memories(user_id)
    return [
        MemoryOut(
            id=m.id,
            type=m.type,
            category=m.category,
            content=m.content,
            importance=m.importance,
        )
        for m in items
    ]
