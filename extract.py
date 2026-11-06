"""
All Gemini text calls, with a disk cache (cache.py) so the same question is never paid for twice.

  extract()            conversation -> structured knowledge (filter + extraction)
  classify_relations() new tip + older similar tips -> how they relate (same / narrows / supersedes / conflicts)
"""
import os
import time

from google import genai
from google.genai import types

import cache
from prompts import FEW_SHOT_EXAMPLES, RELATION_INSTRUCTION, SYSTEM_INSTRUCTION, build_prompt
from schema import ExtractionResult, RelationResult

_client = None


def client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


def _model() -> str:
    return os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def _generate(prompt: str, system_instruction: str, schema, retries: int = 4):
    for attempt in range(retries):
        try:
            response = client().models.generate_content(
                model=_model(),
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=schema,
                    temperature=0,
                ),
            )
            if response.parsed is not None:
                return response.parsed
            return schema.model_validate_json(response.text)
        except Exception as e:  # free tier rate limits are common: wait and retry
            wait = 2 ** attempt * 5
            print(f"  Gemini error ({e.__class__.__name__}: {e}); retrying in {wait}s")
            time.sleep(wait)
    raise RuntimeError("Gemini call failed after retries")


def extract(conversation_text: str, device_context: str, vocabulary_text: str) -> ExtractionResult:
    # The cache key ignores the vocabulary list (it grows during a run) but includes the
    # instructions, so editing the prompt automatically invalidates old answers.
    key = cache.make_key(_model(), SYSTEM_INSTRUCTION, FEW_SHOT_EXAMPLES, conversation_text, device_context)
    hit = cache.get("extract", key)
    if hit is not None:
        print("  (extraction from cache)")
        return ExtractionResult.model_validate(hit)
    result = _generate(build_prompt(conversation_text, device_context, vocabulary_text),
                       SYSTEM_INSTRUCTION, ExtractionResult)
    cache.put("extract", key, result.model_dump())
    return result


def classify_relations(prompt: str) -> RelationResult:
    key = cache.make_key(_model(), RELATION_INSTRUCTION, prompt)
    hit = cache.get("relations", key)
    if hit is not None:
        print("  (relations from cache)")
        return RelationResult.model_validate(hit)
    result = _generate(prompt, RELATION_INSTRUCTION, RelationResult)
    cache.put("relations", key, result.model_dump())
    return result
