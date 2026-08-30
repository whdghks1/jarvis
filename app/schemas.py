from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, from_attributes=True)


class ChatRequest(ApiModel):
    message: str = Field(min_length=1, max_length=20_000)
    conversation_id: int | None = Field(default=None, gt=0)


class ChatResponse(ApiModel):
    reply: str
    conversation_id: int


class MemoryCreate(ApiModel):
    content: str = Field(min_length=1, max_length=4000)
    type: Literal["fact", "preference", "goal", "project", "person", "decision"] = "fact"
    category: str = Field(default="general", min_length=1, max_length=100)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    normalized_key: str | None = Field(default=None, min_length=1, max_length=200)


class MemoryOut(ApiModel):
    id: int
    type: str
    category: str
    content: str
    importance: float
    normalized_key: str | None = None


class MemoryUpdate(ApiModel):
    content: str | None = Field(default=None, min_length=1, max_length=4000)
    type: Literal["fact", "preference", "goal", "project", "person", "decision"] | None = None
    category: str | None = Field(default=None, min_length=1, max_length=100)
    importance: float | None = Field(default=None, ge=0.0, le=1.0)
    normalized_key: str | None = Field(default=None, min_length=1, max_length=200)


class ConversationCreate(ApiModel):
    title: str | None = Field(default=None, max_length=200)


class ConversationOut(ApiModel):
    id: int
    title: str | None
    summary: str | None


class MessageOut(ApiModel):
    id: int
    role: str
    content: str


class ProfileUpdate(ApiModel):
    display_name: str | None = Field(default=None, max_length=100)
    timezone: str | None = Field(default=None, max_length=100)
    locale: str | None = Field(default=None, max_length=20)
    preferred_language: str | None = Field(default=None, max_length=50)


class ProfileOut(ApiModel):
    display_name: str | None
    timezone: str
    locale: str
    preferred_language: str
