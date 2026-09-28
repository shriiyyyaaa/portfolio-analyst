"""
Thin wrapper around OpenRouter's chat completions endpoint.

OpenRouter exposes an OpenAI-compatible API, so we talk to it with plain
httpx POST requests instead of pulling in the full openai SDK - one fewer
dependency, and it keeps exactly what's sent/received visible, which
matters for the latency logging this project needs anyway.
"""
import time

import httpx

from app.config import settings

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class ModelCallResult:
    def __init__(self, content, tool_calls, latency_ms, prompt_tokens, completion_tokens, model_used):
        self.content = content
        self.tool_calls = tool_calls or []
        self.latency_ms = latency_ms
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.model_used = model_used


def call_model(messages: list, tools: list = None, model: str = None) -> ModelCallResult:
    """
    Calls OpenRouter once and returns the result. No retry/looping here -
    app/agent.py owns the multi-turn tool-calling loop; this function just
    makes one HTTP call and reports how long it took.
    """
    model = model or settings.default_model
    payload = {"model": model, "messages": messages}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "AI Real Estate Portfolio Analyst",
    }

    start = time.monotonic()
    with httpx.Client(timeout=40) as client:
        resp = client.post(OPENROUTER_URL, headers=headers, json=payload)
    latency_ms = int((time.monotonic() - start) * 1000)

    if resp.status_code != 200:
        raise RuntimeError(f"OpenRouter error {resp.status_code}: {resp.text[:500]}")

    data = resp.json()
    choice = data["choices"][0]["message"]
    usage = data.get("usage", {})

    return ModelCallResult(
        content=choice.get("content"),
        tool_calls=choice.get("tool_calls"),
        latency_ms=latency_ms,
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
        model_used=data.get("model", model),
    )


class ModelUnavailable(Exception):
    """Raised when the model could not be reached after retrying."""


def call_model_resilient(messages: list, tools: list = None) -> ModelCallResult:
    """
    Two attempts: the primary model, then (if FALLBACK_MODEL is set) a different
    model, otherwise the primary again. Stops a transient 429 / 5xx / timeout from
    turning into a raw server error for the user.
    """
    attempts = [settings.default_model, settings.fallback_model or settings.default_model]
    last_error = None
    for i, model in enumerate(attempts):
        try:
            return call_model(messages, tools=tools, model=model)
        except Exception as exc:  # network errors, timeouts, non-200 responses
            last_error = exc
            if i < len(attempts) - 1:
                time.sleep(1.0)
    raise ModelUnavailable(str(last_error))
