from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    user_id: str = "owner"


class ChatResponse(BaseModel):
    reply: str


class MemoryCreate(BaseModel):
    """A structured memory that can be saved without calling the AI agent."""

    model_config = ConfigDict(str_strip_whitespace=True)

    user_id: str = Field(default="owner", min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=4000)
    type: Literal["fact", "preference", "goal", "project", "person", "decision"] = (
        "fact"
    )
    category: str = Field(default="general", min_length=1, max_length=100)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)


class MemoryOut(BaseModel):
    id: int
    type: str
    category: str
    content: str
    importance: float
