"""
scripts/verify_qwen.py

Quick smoke test for the Qwen Cloud function-calling (tools API) path.
Run this after setting QWEN_API_KEY in your .env to confirm that:
  1. your key works against the DashScope international endpoint, and
  2. qwen-plus returns a forced, schema-valid tool call.

Usage:
    python scripts/verify_qwen.py
"""

import os
import sys
from pathlib import Path

# make the repo root importable when run from anywhere
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from agents.llm_utils import call_llm_tool


def main() -> int:
    api_key = os.getenv("QWEN_API_KEY")
    if not api_key:
        print("✗ QWEN_API_KEY not set. Add it to your .env and retry.")
        return 1

    try:
        from openai import OpenAI
    except ImportError:
        print("✗ openai package not installed. Run: pip install -r requirements.txt")
        return 1

    client = OpenAI(
        api_key=api_key,
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    )

    tool = {
        "name": "record_job_match",
        "description": "Record a structured job-match assessment.",
        "parameters": {
            "type": "object",
            "properties": {
                "score":    {"type": "integer", "minimum": 0, "maximum": 100},
                "decision": {"type": "string", "enum": ["APPLY", "REVIEW", "SKIP"]},
                "reasoning": {"type": "string"},
            },
            "required": ["score", "decision", "reasoning"],
        },
    }

    messages = [
        {"role": "system", "content": "You score how well a candidate matches a job."},
        {"role": "user", "content": (
            "CANDIDATE: Python/Django developer, 1 year experience.\n"
            "JOB: Junior Backend Developer (Python, Django), Harare."
        )},
    ]

    print("→ Calling qwen-plus with function-calling (tools API)...")
    try:
        result = call_llm_tool(client, "qwen-plus", messages, tool, max_tokens=300)
    except Exception as e:
        print(f"✗ Qwen call failed: {type(e).__name__}: {e}")
        print("  Check: key validity, model name (qwen-plus), network, and remaining quota.")
        return 1

    print("✓ Qwen function-calling works. Structured result:")
    for k in ("score", "decision", "reasoning"):
        print(f"    {k}: {result.get(k)}")

    ok = isinstance(result.get("score"), int) and result.get("decision") in {"APPLY", "REVIEW", "SKIP"}
    print("\n✓ PASS — schema-valid tool call returned." if ok
          else "\n⚠ Call returned, but fields look off — inspect the result above.")
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
