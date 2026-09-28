"""
Interactive terminal chat - talk to your agent right now, before we build
any UI. Makes real calls to OpenRouter, so OPENROUTER_API_KEY must be set
in your .env.

Run from backend/ (venv active):
    python chat_cli.py
"""
from app.agent import handle_user_message
from app.database import Base, SessionLocal, engine
from app.models import Conversation, Message, ModelCall, ToolCall, User
from app.seed import load_properties, load_users

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# Safe to re-run (see app/seed.py) - makes sure the dataset is loaded.
load_users(db)
load_properties(db)

print("Available users: U001 (Rahul Mehta), U002 (Priya Shah), U003 (Arjun Kapoor), U004 (Neha Jain)")
user_id = input("Which user_id are you chatting as? ").strip().upper()
if db.get(User, user_id) is None:
    print(f"Unknown user_id {user_id}. Exiting.")
    raise SystemExit(1)

conversation = Conversation(user_id=user_id)
db.add(conversation)
db.commit()
print(f"\nStarted conversation #{conversation.id}. Type 'exit' to quit.\n")

while True:
    text = input("You: ").strip()
    if text.lower() in ("exit", "quit"):
        break
    if not text:
        continue

    db.add(Message(conversation_id=conversation.id, role="user", content=text))
    db.commit()

    try:
        result = handle_user_message(db, user_id, conversation.id, text)
    except Exception as exc:
        print(f"\n[error] {exc}\n")
        continue

    assistant_msg = Message(conversation_id=conversation.id, role="assistant", content=result["final_text"])
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    for log in result["tool_call_logs"]:
        db.add(ToolCall(message_id=assistant_msg.id, **log))
    for mc in result["model_call_logs"]:
        db.add(ModelCall(
            message_id=assistant_msg.id,
            model=mc.model_used,
            latency_ms=mc.latency_ms,
            prompt_tokens=mc.prompt_tokens,
            completion_tokens=mc.completion_tokens,
            success=True,
        ))
    db.commit()

    print(f"\nAssistant: {result['final_text']}\n")

    if result["tool_call_logs"]:
        names = ", ".join(t["tool_name"] for t in result["tool_call_logs"])
        tool_ms = sum(t["latency_ms"] for t in result["tool_call_logs"])
        model_ms = sum(mc.latency_ms for mc in result["model_call_logs"])
        print(f"[debug] tools called: {names} | tool time: {tool_ms}ms | model time: {model_ms}ms\n")
