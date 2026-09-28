
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    user_id = Column(String, primary_key=True)
    name = Column(String, nullable=True)
    city = Column(String, nullable=True)
    stated_preferences = Column(Text, nullable=True)
    preferred_locations = Column(Text, nullable=True)
    portfolio_value_preference = Column(String, nullable=True)

    properties = relationship("Property", back_populates="owner")
    conversations = relationship("Conversation", back_populates="user")


class Property(Base):
    __tablename__ = "properties"

    property_id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)

    property_type = Column(String, nullable=False)      
    sub_type = Column(String, nullable=True)            
    normalized_type = Column(String, nullable=True)     

    location = Column(String, nullable=False)            
    area_sqft = Column(Float, nullable=True)

    current_estimated_value_inr = Column(Float, nullable=True)
    purchase_price_inr = Column(Float, nullable=True)     
    annual_rent_inr = Column(Float, nullable=True)

    occupancy_status = Column(String, nullable=True)
    tenant_status = Column(String, nullable=True)
    ownership_percent = Column(Float, nullable=True)
    status = Column(String, nullable=True)

    owner = relationship("User", back_populates="properties")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    needs_attention = Column(Boolean, default=False)
    attention_reason = Column(String, nullable=True)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", order_by="Message.id")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)  # "user" | "assistant" | "system"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")
    tool_calls = relationship("ToolCall", back_populates="message")
    model_calls = relationship("ModelCall")


class ToolCall(Base):
    """
    Every time the agent calls a deterministic tool, we log it here.
    This table IS the observability layer the admin UI reads from -
    no separate logging infra needed for a project this size.
    """
    __tablename__ = "tool_calls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    tool_name = Column(String, nullable=False)
    arguments_json = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    success = Column(Boolean, default=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    message = relationship("Message", back_populates="tool_calls")


class ModelCall(Base):
    """Logs every call to the model gateway (OpenRouter) for latency/cost tracking."""
    __tablename__ = "model_calls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False)
    model = Column(String, nullable=False)
    latency_ms = Column(Integer, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    success = Column(Boolean, default=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
