"""Shared response parser for extracting JSON from agent output."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def parse_agent_response(content: str) -> dict[str, Any]:
    """Extract JSON from agent response text, handling various formats robustly.

    Strategies tried in order:
    1. ```json ... ``` code blocks
    2. ``` ... ``` code blocks (no language tag)
    3. Largest balanced { ... } JSON object in the text
    4. Entire text as JSON
    5. Fallback: wrap raw text with parse_error flag + raw_response
    """
    text = content.strip()

    # Strategy 1: ```json ... ``` blocks
    json_blocks = re.findall(r"```json\s*(.*?)```", text, re.DOTALL)
    if json_blocks:
        for block in json_blocks:
            try:
                return json.loads(block.strip())
            except json.JSONDecodeError:
                continue

    # Strategy 2: ``` ... ``` blocks
    code_blocks = re.findall(r"```\s*(.*?)```", text, re.DOTALL)
    if code_blocks:
        for block in code_blocks:
            try:
                return json.loads(block.strip())
            except json.JSONDecodeError:
                continue

    # Strategy 3: largest balanced { ... } JSON object
    best_json: dict[str, Any] | None = None
    for match in re.finditer(r"\{", text):
        start = match.start()
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            c = text[i]
            if escape:
                escape = False
                continue
            if c == "\\":
                escape = True
                continue
            if c == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        parsed = json.loads(candidate)
                        if best_json is None or len(candidate) > len(
                            json.dumps(best_json)
                        ):
                            best_json = parsed
                    except json.JSONDecodeError:
                        pass
                    break
    if best_json is not None:
        return best_json

    # Strategy 4: entire text as JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback — log the failure prominently so it doesn't go unnoticed
    preview = text[:500].replace("\n", " ")
    logger.warning(
        f"[PARSE FAIL] Could not extract JSON from LLM response ({len(text)} chars). "
        f"Preview: {preview}"
    )
    return {"raw_response": content, "parse_error": True}
