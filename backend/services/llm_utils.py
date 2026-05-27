"""
LLM Utilities
=============
Shared utilities for all services that call Claude.
Centralises: client singleton, JSON response parsing, retry helpers.

Previously these were private functions inside classifier.py that other
services imported — which created coupling. Now they live here.
"""

import json
import re
from typing import Optional

import structlog
from anthropic import AsyncAnthropic

logger = structlog.get_logger(__name__)

_anthropic_client: Optional[AsyncAnthropic] = None


def get_anthropic_client() -> AsyncAnthropic:
    """
    Return the singleton Anthropic client.
    Initialised lazily on first call so settings are loaded first.
    """
    global _anthropic_client
    if _anthropic_client is None:
        from config import get_settings
        settings = get_settings()
        _anthropic_client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _anthropic_client


def parse_json_response(content: str) -> dict | list:
    """
    Parse JSON from a Claude response, handling common edge cases:
    - Markdown code fences (```json ... ```)
    - Leading/trailing whitespace and BOM characters
    - Mixed prose + JSON (extracts the JSON object/array)

    Raises ValueError if no valid JSON can be extracted.
    """
    # Strip BOM and whitespace
    content = content.strip().lstrip("\ufeff")

    # Strip markdown code fences
    if content.startswith("```"):
        lines = content.split("\n")
        inner = lines[1:]
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        content = "\n".join(inner).strip()

    # Try direct parse first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try to extract a JSON object
    obj_match = re.search(r"\{.*\}", content, re.DOTALL)
    if obj_match:
        try:
            return json.loads(obj_match.group())
        except json.JSONDecodeError:
            pass

    # Try to extract a JSON array
    arr_match = re.search(r"\[.*\]", content, re.DOTALL)
    if arr_match:
        try:
            return json.loads(arr_match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(
        f"Could not extract valid JSON from response. "
        f"First 300 chars: {content[:300]!r}"
    )
