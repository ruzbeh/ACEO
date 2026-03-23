"""Shared response parser for extracting JSON from agent output.

Eliminates systematic parse errors by:
- Extracting JSON from markdown code blocks and raw text
- Trying strict json.loads() first, then json_repair.loads() for malformed output
  (trailing commas, single quotes, unquoted keys, Python literals, truncation)
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Optional: use json_repair for LLM-style malformed JSON (trailing commas, single quotes, etc.)
def _repair_loads(candidate: str) -> dict[str, Any] | None:
    """Parse JSON, trying strict first then repair. Returns None on failure."""
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    try:
        import json_repair
        return json_repair.loads(candidate)
    except Exception:  # ImportError or json_repair failure
        return None


def parse_agent_response(content: str) -> dict[str, Any]:
    """Extract JSON from agent response text, handling various formats robustly.

    For each candidate (code block, balanced {...}, or full text):
    - Tries json.loads() first
    - If that fails, tries json_repair.loads() to fix trailing commas,
      single quotes, unquoted keys, Python True/False/None, truncation, etc.
    """
    if not content or not isinstance(content, str):
        return {"raw_response": content or "", "parse_error": True}

    text = content.strip()
    if not text:
        return {"raw_response": content, "parse_error": True}

    # Normalize: strip BOM, collapse stray nulls
    if text.startswith("\ufeff"):
        text = text[1:].strip()

    # Strategy 1: ```json ... ``` blocks
    json_blocks = re.findall(r"```json\s*(.*?)```", text, re.DOTALL)
    for block in json_blocks:
        parsed = _repair_loads(block.strip())
        if parsed is not None and isinstance(parsed, dict):
            return parsed

    # Strategy 2: ``` ... ``` blocks (no language tag)
    code_blocks = re.findall(r"```\s*(.*?)```", text, re.DOTALL)
    for block in code_blocks:
        stripped = block.strip()
        if stripped.startswith("{"):
            parsed = _repair_loads(stripped)
            if parsed is not None and isinstance(parsed, dict):
                return parsed

    # Strategy 3: largest balanced { ... } JSON object
    best_json: dict[str, Any] | None = None
    best_len = 0
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
                    parsed = _repair_loads(candidate)
                    if parsed is not None and isinstance(parsed, dict) and len(candidate) > best_len:
                        best_json = parsed
                        best_len = len(candidate)
                    break
    if best_json is not None:
        return best_json

    # Strategy 4: entire text as JSON (strict or repair)
    parsed = _repair_loads(text)
    if parsed is not None and isinstance(parsed, dict):
        return parsed

    # Strategy 5: let json_repair try to extract from noisy text (e.g. leading/trailing prose)
    try:
        import json_repair
        parsed = json_repair.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # Strategy 6: heuristic field extraction from raw text
    # Extract key structured fields even when JSON is malformed
    heuristic = _heuristic_extract(text)
    if heuristic:
        logger.info(
            "[PARSE HEURISTIC] Extracted %d fields from raw text (%d chars)",
            len(heuristic), len(text),
        )
        heuristic["parse_error"] = False
        heuristic["parse_method"] = "heuristic"
        return heuristic

    # Fallback — log once so it doesn't go unnoticed
    preview = text[:500].replace("\n", " ")
    logger.warning(
        "[PARSE FAIL] Could not extract JSON from LLM response (%d chars). Preview: %s",
        len(text),
        preview,
    )
    return {"raw_response": content, "parse_error": True}


def _heuristic_extract(text: str) -> dict[str, Any] | None:
    """Last-resort: extract key agent output fields using regex patterns.

    Returns a dict with at least 'decision' if anything useful was found, else None.
    """
    result: dict[str, Any] = {}

    # Try to extract decision/summary
    for pattern in [
        r'(?:decision|summary|conclusion)\s*[:=]\s*["\'](.+?)["\']',
        r'(?:Decision|Summary|Conclusion):\s*(.+?)(?:\n|$)',
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            result["decision"] = m.group(1).strip()[:500]
            break

    # Extract confidence
    m = re.search(r'(?:confidence)\s*[:=]\s*(0\.\d+|\d(?:\.\d+)?)', text, re.IGNORECASE)
    if m:
        try:
            result["confidence"] = float(m.group(1))
        except ValueError:
            pass

    # Extract verdict (for evaluator)
    m = re.search(r'(?:verdict)\s*[:=]\s*["\']?(scale|iterate|kill)["\']?', text, re.IGNORECASE)
    if m:
        result["verdict"] = m.group(1).lower()

    # Extract approved (for QA)
    m = re.search(r'(?:approved)\s*[:=]\s*(true|false)', text, re.IGNORECASE)
    if m:
        result["approved"] = m.group(1).lower() == "true"

    # Extract escalate (for fast-track architect)
    m = re.search(r'(?:escalate)\s*[:=]\s*(true|false)', text, re.IGNORECASE)
    if m:
        result["escalate"] = m.group(1).lower() == "true"

    if not result or "decision" not in result:
        # If we couldn't even get a decision, try using the first meaningful line
        for line in text.split("\n"):
            line = line.strip()
            if len(line) > 20 and not line.startswith(("```", "#", "---", "***")):
                result["decision"] = line[:500]
                break

    if not result:
        return None

    # Fill defaults
    result.setdefault("decision", "Task completed (heuristic parse)")
    result.setdefault("assumptions", [])
    result.setdefault("risks", [])
    result.setdefault("confidence", 0.5)
    return result


def extract_code_artifacts_from_text(text: str) -> list[dict[str, Any]]:
    """Extract code blocks from raw response text when JSON parse fails.

    Returns a list of {"path": str, "content": str} for each ```...``` block.
    If the first line of a block looks like a path (e.g. path/to/file.py), use it; else snippet_N.
    """
    if not text or not text.strip():
        return []
    artifacts: list[dict[str, Any]] = []
    # Match ```optional_lang_or_path\ncontent```
    pattern = re.compile(r"```(?:\w+)?\s*(.*?)```", re.DOTALL)
    for i, block in enumerate(pattern.findall(text)):
        block = block.strip()
        if not block:
            continue
        lines = block.split("\n", 1)
        first_line = lines[0].strip()
        content = lines[1] if len(lines) > 1 else ""
        # Use first line as path if it looks like a file path (has slash or ends with extension)
        if (
            "/" in first_line
            or first_line.endswith(".py")
            or first_line.endswith(".ts")
            or first_line.endswith(".tsx")
            or first_line.endswith(".js")
            or first_line.endswith(".jsx")
            or first_line.endswith(".html")
            or first_line.endswith(".css")
            or first_line.endswith(".json")
            or first_line.endswith(".yaml")
            or first_line.endswith(".yml")
            or first_line.endswith(".md")
            or first_line.endswith(".sh")
        ):
            path = first_line.lstrip("./")
            body = content
        else:
            path = f"snippet_{len(artifacts) + 1}.txt"
            body = block
        if body:
            artifacts.append({"path": path, "content": body})
    return artifacts
