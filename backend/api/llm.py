"""Gemini helpers for the chat (JSON and streamed text), with disk cache and retries on
rate limits / overload. Reuses the client from pipeline/extract.py."""
import logging
import re
import time

from google.genai import types

from pipeline import cache
from api.config import CACHE_ANSWERS, CHAT_MODEL, GEMINI_MAX_WAIT, GEMINI_RETRIES, THINKING_BUDGET
from pipeline.extract import _model, client

log = logging.getLogger("api.llm")
_thinking_ok = True


def _chat_model() -> str:
    """API_GEMINI_MODEL if set, else the capture model (GEMINI_MODEL)."""
    return CHAT_MODEL or _model()


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
        msg = str(e).lower()
        if _thinking_ok and ("thinking" in msg or "invalid_argument" in msg or getattr(e, "code", None) == 400):
            log.warning("Model rejected thinking_budget; continuing without it")
            _thinking_ok = False
            return fn()
        raise


_NO_RETRY_CODES = {400, 401, 403, 404}


def _retryable(e: Exception) -> bool:
    code = getattr(e, "code", None) or getattr(e, "status_code", None)
    return not (isinstance(code, int) and code in _NO_RETRY_CODES)


def _wait_for(e: Exception, attempt: int) -> float:
    """Seconds to wait: Gemini's own retryDelay if it gives one (429), else 5, 10, 20, 30, 30..."""
    m = re.search(r"retry(?:Delay)?['\"]?\s*[:=]?\s*['\"]?(?:in\s+)?(\d+(?:\.\d+)?)\s*s", str(e), re.IGNORECASE)
    if m:
        return min(GEMINI_MAX_WAIT, float(m.group(1)) + 1)
    return min(GEMINI_MAX_WAIT, 5 * 2 ** attempt)


def with_retries(fn, what: str):
    """Run fn() until it works: rate limits and overloads are waited out, not given up on."""
    for attempt in range(GEMINI_RETRIES):
        try:
            return _call(fn)
        except Exception as e:
            if not _retryable(e) or attempt == GEMINI_RETRIES - 1:
                raise
            wait = _wait_for(e, attempt)
            log.warning("%s: Gemini %s: %s - retry %d/%d in %.0fs", what, e.__class__.__name__,
                        str(e)[:160], attempt + 1, GEMINI_RETRIES - 1, wait)
            time.sleep(wait)


def generate_json(prompt: str, system: str, schema, namespace: str):
    """Structured output (Step A). Returns an instance of `schema`.

    The schema is part of the cache key: when fields are added (e.g. wants_overview), answers cached for
    the old schema must not be reused, or the new fields would silently get their defaults."""
    key = cache.make_key(_chat_model(), system, prompt, schema.model_json_schema())
    hit = cache.get(namespace, key)
    if hit is not None:
        return schema.model_validate(hit)

    def call():
        resp = client().models.generate_content(
            model=_chat_model(), contents=prompt,
            config=_config(system, response_mime_type="application/json", response_schema=schema, temperature=0))
        return resp.parsed if resp.parsed is not None else schema.model_validate_json(resp.text)

    result = with_retries(call, "Step A")
    cache.put(namespace, key, result.model_dump())
    return result


def stream_text(prompt: str, system: str, namespace: str = "api_answer"):
    """Streams the answer text (Step C) chunk by chunk."""
    key = cache.make_key(_chat_model(), system, prompt)
    if CACHE_ANSWERS:
        hit = cache.get(namespace, key)
        if hit is not None:
            text = hit["text"]
            for i in range(0, len(text), 24):
                time.sleep(0.02)
                yield text[i:i + 24]
            return

    parts: list[str] = []

    def first_chunk():
        """Open the stream and read its first chunk: most rate-limit errors arrive here, before any
        text was shown, so the whole call can be retried safely."""
        stream = iter(client().models.generate_content_stream(
            model=_chat_model(), contents=prompt, config=_config(system, temperature=0.2)))
        return stream, next(stream, None)

    stream, chunk = with_retries(first_chunk, "Step C")
    while chunk is not None:
        text = chunk.text or ""
        if text:
            parts.append(text)
            yield text
        chunk = next(stream, None)
    if CACHE_ANSWERS and parts:
        cache.put(namespace, key, {"text": "".join(parts)})
