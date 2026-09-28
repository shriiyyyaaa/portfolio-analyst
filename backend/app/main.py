
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.admin_auth import create_admin_token, verify_admin_token
from app.agent import handle_user_message
from app.config import settings
from app.database import Base, SessionLocal, engine, get_db
from app.models import Conversation, Message, ModelCall, ToolCall, User
from app.schemas import (
    AdminLoginRequest,
    AdminLoginResponse,
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationSummary,
    MessageDetail,
    MessageOut,
    ModelCallOut,
    ToolCallOut,
    UserSummary,
)
from app.seed import load_properties, load_users
from app import models  # noqa: F401 - import so tables register with Base

app = FastAPI(title="AI Real Estate Portfolio Analyst")

# Allowed origins come from CORS_ORIGINS ("*" for local dev; set to the frontend URL in production).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    # Seed the provided dataset only into an EMPTY database, so a restart never overwrites
    # edits made through the chat. (python -m app.seed force-reloads the CSVs.)
    db = SessionLocal()
    try:
        if db.query(User).count() == 0:
            load_users(db)
            load_properties(db)
    finally:
        db.close()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    user = db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"Unknown user_id: {payload.user_id}")

    conversation = db.get(Conversation, payload.conversation_id) if payload.conversation_id else None
    if conversation is not None and conversation.user_id != payload.user_id:
        raise HTTPException(status_code=404, detail="Conversation not found for this user")
    if conversation is None:
        # No id, or an id this server no longer has (e.g. the database was reset): start fresh.
        conversation = Conversation(user_id=payload.user_id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    db.add(Message(conversation_id=conversation.id, role="user", content=payload.message))
    db.commit()

    result = handle_user_message(db, payload.user_id, conversation.id, payload.message)

    assistant_msg = Message(conversation_id=conversation.id, role="assistant", content=result["final_text"])
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    needs_attention = False
    attention_reason = None
    for log in result["tool_call_logs"]:
        db.add(ToolCall(message_id=assistant_msg.id, **log))
        if not log["success"]:
            needs_attention = True
            attention_reason = "A tool call failed during this conversation."
    if result["final_text"].startswith("I ran into trouble"):
        needs_attention = True
        attention_reason = attention_reason or "The agent could not complete a request within its tool-call limit."
    if result.get("model_error"):
        needs_attention = True
        attention_reason = "Model unavailable: " + result["model_error"][:200]
    for mc in result["model_call_logs"]:
        db.add(ModelCall(
            message_id=assistant_msg.id,
            model=mc.model_used,
            latency_ms=mc.latency_ms,
            prompt_tokens=mc.prompt_tokens,
            completion_tokens=mc.completion_tokens,
            success=True,
        ))
    if needs_attention:
        conversation.needs_attention = True
        conversation.attention_reason = attention_reason
    db.commit()

    return ChatResponse(conversation_id=conversation.id, reply=result["final_text"])


@app.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def get_messages(conversation_id: int, user_id: str, db: Session = Depends(get_db)):
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user_id:
        raise HTTPException(status_code=404, detail="Conversation not found for this user")
    return conversation.messages


# --- Admin ---

def require_admin(authorization: Optional[str] = Header(None)):
    """
    FastAPI dependency gating every /admin/* route. See app/admin_auth.py
    for why this is a single shared password rather than per-admin accounts.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing admin token")
    token = authorization[len("Bearer "):].strip()
    if not settings.admin_password or not verify_admin_token(token, settings.admin_password):
        raise HTTPException(status_code=401, detail="Invalid or expired admin token")


@app.post("/admin/login", response_model=AdminLoginResponse)
def admin_login(payload: AdminLoginRequest):
    if not settings.admin_password:
        raise HTTPException(status_code=500, detail="ADMIN_PASSWORD is not configured on the server")
    if payload.password != settings.admin_password:
        raise HTTPException(status_code=401, detail="Incorrect password")
    return AdminLoginResponse(token=create_admin_token(settings.admin_password))


@app.get("/admin/users", response_model=list[UserSummary], dependencies=[Depends(require_admin)])
def admin_list_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [
        UserSummary(
            user_id=u.user_id,
            name=u.name,
            city=u.city,
            property_count=len(u.properties),
            total_value_inr=sum((p.current_estimated_value_inr or 0) for p in u.properties),
        )
        for u in users
    ]


@app.get("/admin/conversations", response_model=list[ConversationSummary], dependencies=[Depends(require_admin)])
def admin_list_conversations(
    user_id: Optional[str] = None,
    needs_attention: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Conversation)
    if user_id:
        query = query.filter(Conversation.user_id == user_id)
    if needs_attention is not None:
        query = query.filter(Conversation.needs_attention == needs_attention)
    conversations = query.order_by(Conversation.id.desc()).all()

    result = []
    for c in conversations:
        user = db.get(User, c.user_id)
        last = c.messages[-1].content if c.messages else None
        result.append(ConversationSummary(
            id=c.id,
            user_id=c.user_id,
            user_name=user.name if user else None,
            created_at=c.created_at,
            message_count=len(c.messages),
            needs_attention=c.needs_attention,
            attention_reason=c.attention_reason,
            last_message_preview=(last[:120] + "…") if last and len(last) > 120 else last,
        ))
    return result


@app.get(
    "/admin/conversations/{conversation_id}",
    response_model=ConversationDetail,
    dependencies=[Depends(require_admin)],
)
def admin_get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    c = db.get(Conversation, conversation_id)
    if c is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = [
        MessageDetail(
            role=m.role,
            content=m.content,
            created_at=m.created_at,
            tool_calls=[ToolCallOut.model_validate(tc) for tc in m.tool_calls],
            model_calls=[ModelCallOut.model_validate(mc) for mc in m.model_calls],
        )
        for m in c.messages
    ]
    return ConversationDetail(
        id=c.id,
        user_id=c.user_id,
        needs_attention=c.needs_attention,
        attention_reason=c.attention_reason,
        messages=messages,
    )
