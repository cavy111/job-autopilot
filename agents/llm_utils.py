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


def call_llm_tool(client, model, messages, tool, temperature=0.1, max_tokens=800):
    """
    Call a Qwen model and force it to return structured data via a function
    (tool) call, using the OpenAI-compatible tools API exposed by Qwen Cloud /
    DashScope. Returns the parsed arguments dict.

    `tool` is a function definition, e.g.:
        {"name": "record_match",
         "description": "...",
         "parameters": { ...JSON schema... }}

    Falls back to parsing free-text JSON from the message content if the model
    returns content instead of a tool call, so callers get a dict either way.
    """
    name = tool["name"]
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=[{"type": "function", "function": tool}],
        tool_choice={"type": "function", "function": {"name": name}},
        temperature=temperature,
        max_tokens=max_tokens,
    )
    msg = response.choices[0].message
    tool_calls = getattr(msg, "tool_calls", None)
    if tool_calls:
        try:
            return json.loads(tool_calls[0].function.arguments)
        except json.JSONDecodeError:
            return parse_llm_json(tool_calls[0].function.arguments)
    if getattr(msg, "content", None):
        return parse_llm_json(msg.content)
    logger.error("LLM returned neither a tool call nor content.")
    raise ValueError("LLM returned no structured output. Try running again.")
