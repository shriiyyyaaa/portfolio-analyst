from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    user_id: str
    conversation_id: Optional[int] = None
    message: str


class ChatResponse(BaseModel):
    conversation_id: int
    reply: str


class MessageOut(BaseModel):
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


# --- Admin schemas ---

class AdminLoginRequest(BaseModel):
    password: str


class AdminLoginResponse(BaseModel):
    token: str


class UserSummary(BaseModel):
    user_id: str
    name: Optional[str] = None
    city: Optional[str] = None
    property_count: int
    total_value_inr: float


class ConversationSummary(BaseModel):
    id: int
    user_id: str
    user_name: Optional[str] = None
    created_at: datetime
    message_count: int
    needs_attention: bool
    attention_reason: Optional[str] = None
    last_message_preview: Optional[str] = None


class ToolCallOut(BaseModel):
    tool_name: str
    arguments_json: Optional[str] = None
    result_json: Optional[str] = None
    latency_ms: Optional[int] = None
    success: bool
    error: Optional[str] = None

    class Config:
        from_attributes = True


class ModelCallOut(BaseModel):
    model: str
    latency_ms: Optional[int] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None

    class Config:
        from_attributes = True


class MessageDetail(BaseModel):
    role: str
    content: str
    created_at: datetime
    tool_calls: list[ToolCallOut] = []
    model_calls: list[ModelCallOut] = []

    class Config:
        from_attributes = True


class ConversationDetail(BaseModel):
    id: int
    user_id: str
    needs_attention: bool
    attention_reason: Optional[str] = None
    messages: list[MessageDetail]
