"""Tests for agent response JSON parsing and repair."""
import pytest
from aeco.agents.response_parser import (
    extract_code_artifacts_from_text,
    parse_agent_response,
)


def test_parse_valid_json_block():
    content = """Here is my analysis.

```json
{"decision": "Proceed", "confidence": 0.9}
```
"""
    out = parse_agent_response(content)
    assert out.get("parse_error") is not True
    assert out["decision"] == "Proceed"
    assert out["confidence"] == 0.9


def test_parse_trailing_comma_repaired():
    # LLMs often output trailing commas; json_repair fixes this
    content = """```json
{
  "decision": "Done",
  "confidence": 0.8,
}
```
"""
    out = parse_agent_response(content)
    assert out.get("parse_error") is not True
    assert out["decision"] == "Done"
    assert out["confidence"] == 0.8


def test_parse_single_quotes_repaired():
    content = """```json
{'key': 'value', 'n': 42}
```
"""
    out = parse_agent_response(content)
    assert out.get("parse_error") is not True
    assert out["key"] == "value"
    assert out["n"] == 42


def test_parse_largest_balanced_brace_object():
    content = "Before {\"a\": 1} after {\"b\": 2, \"c\": 3} end"
    out = parse_agent_response(content)
    assert out.get("parse_error") is not True
    # Should pick the larger object
    assert "b" in out and "c" in out


def test_parse_empty_returns_parse_error():
    out = parse_agent_response("")
    assert out.get("parse_error") is True
    assert "raw_response" in out


def test_parse_no_json_uses_heuristic_fallback():
    out = parse_agent_response("I cannot provide a structured response today.")
    # Heuristic extraction now recovers a decision from raw text
    assert out.get("decision") is not None
    assert out.get("parse_method") == "heuristic"


def test_parse_truly_empty_returns_parse_error():
    out = parse_agent_response("ok")
    # Very short text with no useful fields still returns parse_error
    assert out.get("parse_error") is True or out.get("parse_method") == "heuristic"


def test_extract_code_artifacts_from_text():
    text = """
    ```python
    src/main.py
    def hello():
        print("hi")
    ```
    ```
    foo.ts
    export const x = 1;
    ```
    """
    artifacts = extract_code_artifacts_from_text(text)
    assert len(artifacts) == 2
    assert artifacts[0]["path"] == "src/main.py"
    assert "def hello" in artifacts[0]["content"]
    assert artifacts[1]["path"] == "foo.ts"
    assert "export const x" in artifacts[1]["content"]


def test_extract_code_artifacts_empty():
    assert extract_code_artifacts_from_text("") == []
    assert extract_code_artifacts_from_text("no blocks") == []
