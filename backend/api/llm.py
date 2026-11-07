"""
Small Gemini helpers for the chat (re-uses the client and model name from extract.py).
Both helpers use the disk cache (cache.py), so a repeated demo question costs no API calls.
"""
import logging
import time

from google.genai import types

from pipeline import cache
from api.config import CACHE_ANSWERS, THINKING_BUDGET
from pipeline.extract import _model, client

log = logging.getLogger("api.llm")
_thinking_ok = True  # switched off automatically if the model rejects a thinking budget


def _config(system: str, **kw) -> types.GenerateContentConfig:
    if _thinking_ok and THINKING_BUDGET.strip() != "":
        kw["thinking_config"] = types.ThinkingConfig(thinking_budget=int(THINKING_BUDGET))
    return types.GenerateContentConfig(system_instruction=system, **kw)


def _call(fn):
    """Run fn(); if the model doesn't accept the thinking budget, retry once without it."""
    global _thinking_ok
    try:
        return fn()
    except Exception as e:
        if _thinking_ok and "thinking" in str(e).lower():
            log.warning("Model rejected thinking_budget; continuing without it")
            _thinking_ok = False
            return fn()
        raise


def generate_json(prompt: str, system: str, schema, namespace: str, retries: int = 2):
    """Structured output (Step A). Returns an instance of `schema`."""
    key = cache.make_key(_model(), system, prompt)
    hit = cache.get(namespace, key)
    if hit is not None:
        return schema.model_validate(hit)
    last = None
    for attempt in range(retries):
        try:
            resp = _call(lambda: client().models.generate_content(
                model=_model(), contents=prompt,
                config=_config(system, response_mime_type="application/json",
                               response_schema=schema, temperature=0)))
            result = resp.parsed if resp.parsed is not None else schema.model_validate_json(resp.text)
            cache.put(namespace, key, result.model_dump())
            return result
        except Exception as e:  # rate limits etc.
            last = e
            log.warning("Gemini JSON call failed (%s: %s)", e.__class__.__name__, e)
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Gemini call failed: {last}")


def stream_text(prompt: str, system: str, namespace: str = "api_answer"):
    """Streams the answer text (Step C) chunk by chunk."""
    key = cache.make_key(_model(), system, prompt)
    if CACHE_ANSWERS:
        hit = cache.get(namespace, key)
        if hit is not None:
            text = hit["text"]
            for i in range(0, len(text), 24):  # replay in small pieces so the UI still "types"
                time.sleep(0.02)
                yield text[i:i + 24]
            return

    parts: list[str] = []

    def start():
        return client().models.generate_content_stream(
            model=_model(), contents=prompt, config=_config(system, temperature=0.2))

    for chunk in _call(start):
        text = chunk.text or ""
        if text:
            parts.append(text)
            yield text
    if CACHE_ANSWERS and parts:
        cache.put(namespace, key, {"text": "".join(parts)})
