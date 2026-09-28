
import json
import time

from app.llm_client import ModelUnavailable, call_model_resilient
from app.tool_schemas import TOOLS_SCHEMA, execute_tool
from app.system_prompt import SYSTEM_PROMPT
from app.models import Message, User

MAX_TOOL_ITERATIONS = 4   # hard cap so a confused model can't loop forever
HISTORY_WINDOW = 10       # last N stored messages sent back as context


def _recent_history(db, conversation_id: int) -> list:
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.id.desc())
        .limit(HISTORY_WINDOW)
        .all()
    )
    messages.reverse()
    return [{"role": m.role, "content": m.content} for m in messages]


def handle_user_message(db, user_id: str, conversation_id: int, user_text: str) -> dict:
    """
    Runs the full tool-calling loop for one user message and returns:
      {"final_text": str, "tool_call_logs": [...], "model_call_logs": [...]}
    The caller (main.py or chat_cli.py) is responsible for persisting these
    as Message/ToolCall/ModelCall rows - this function is DB-read-heavy but
    only writes through the tool functions themselves.
    """
    user = db.get(User, user_id)
    user_name = user.name if user else user_id

    history = _recent_history(db, conversation_id)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(user_name=user_name)},
        *history,
        {"role": "user", "content": user_text},
    ]

    tool_call_logs = []
    model_call_logs = []
    final_text = None
    model_error = None

    for _ in range(MAX_TOOL_ITERATIONS):
        try:
            result = call_model_resilient(messages, tools=TOOLS_SCHEMA)
        except ModelUnavailable as exc:
            model_error = str(exc)
            final_text = "I'm having trouble reaching the AI model right now. Please try again in a moment."
            if tool_call_logs:
                final_text += (" Note: an action you asked for may already have been applied - "
                               "check your portfolio before repeating it.")
            break
        model_call_logs.append(result)

        if not result.tool_calls:
            final_text = result.content or ""
            break

        messages.append({
            "role": "assistant",
            "content": result.content,
            "tool_calls": result.tool_calls,
        })

        for tc in result.tool_calls:
            fn_name = tc["function"]["name"]
            try:
                fn_args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                fn_args = {}

            start = time.monotonic()
            try:
                tool_result = execute_tool(fn_name, fn_args, user_id, db)
                success, error = True, None
            except Exception as exc:  # surface any failure to the model rather than crashing the request
                tool_result = {"error": str(exc)}
                success, error = False, str(exc)
            latency_ms = int((time.monotonic() - start) * 1000)

            tool_call_logs.append({
                "tool_name": fn_name,
                "arguments_json": json.dumps(fn_args),
                "result_json": json.dumps(tool_result, default=str),
                "latency_ms": latency_ms,
                "success": success,
                "error": error,
            })

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(tool_result, default=str),
            })
    else:
        final_text = "I ran into trouble completing that - could you rephrase or simplify the request?"

    return {
        "final_text": final_text,
        "tool_call_logs": tool_call_logs,
        "model_call_logs": model_call_logs,
        "model_error": model_error,
    }
