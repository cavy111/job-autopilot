"""
agents/llm_utils.py

Shared helpers for parsing structured output from LLM responses.
"""

import json
import re
import logging

logger = logging.getLogger(__name__)


def parse_llm_json(raw: str) -> dict:
    """
    Parse a JSON object out of an LLM response, tolerating markdown code
    fences, a "json" language tag, or stray text before/after the object.

    Raises ValueError (with the offending text logged) if no valid JSON
    object can be extracted, instead of letting a raw JSONDecodeError
    or IndexError bubble up from the caller.
    """
    text = raw.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass

    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    logger.error(f"Could not extract JSON from LLM response: {text[:300]!r}")
    raise ValueError("LLM returned malformed JSON. Try running again.")
