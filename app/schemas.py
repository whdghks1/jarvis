from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    user_id: str = "owner"


class ChatResponse(BaseModel):
    reply: str


class MemoryOut(BaseModel):
    id: int
    type: str
    category: str
    content: str
    importance: float
