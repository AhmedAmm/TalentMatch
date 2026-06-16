"""
security/sanitizers.py
========================
Input-hardening utilities.

Functions
---------
sanitize_string   — strip HTML / script injection, null bytes, control chars
sanitize_dict     — recursively sanitize all string values in a dict / list
check_nosql_injection — reject MongoDB operator injection in any input
"""
from __future__ import annotations

import html
import re
from typing import Any

from fastapi import HTTPException

# Characters that should never appear in free-text user input
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_NULL_BYTE_RE    = re.compile(r"\x00")

# MongoDB operator injection: keys starting with $ or containing dots
_NOSQL_KEY_RE = re.compile(r"^\$|[.]")

# MongoDB operator values that must never appear as literal input
_NOSQL_OPERATORS = {
    "$gt", "$gte", "$lt", "$lte", "$ne", "$in", "$nin",
    "$exists", "$type", "$regex", "$where", "$expr",
    "$and", "$or", "$nor", "$not",
}


def sanitize_string(value: str, max_length: int = 2000) -> str:
    """
    Clean a single string:
      1. Strip leading/trailing whitespace.
      2. Remove null bytes and ASCII control characters.
      3. HTML-escape < > & " ' to their entities (prevents XSS).
      4. Truncate to max_length.
    """
    if not isinstance(value, str):
        return value
    value = value.strip()
    value = _NULL_BYTE_RE.sub("", value)
    value = _CONTROL_CHAR_RE.sub("", value)
    value = html.escape(value, quote=True)
    return value[:max_length]


def sanitize_dict(data: Any, max_length: int = 2000) -> Any:
    """Recursively sanitize all string values inside a dict / list."""
    if isinstance(data, dict):
        return {k: sanitize_dict(v, max_length) for k, v in data.items()}
    if isinstance(data, list):
        return [sanitize_dict(item, max_length) for item in data]
    if isinstance(data, str):
        return sanitize_string(data, max_length)
    return data


def check_nosql_injection(data: Any, _path: str = "root") -> None:
    """
    Walk a dict/list recursively.  Raise HTTPException 400 if any key
    looks like a MongoDB operator (starts with $) or any string value
    is a known MongoDB operator token.

    Call this on every incoming request body before passing to DB helpers.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if _NOSQL_KEY_RE.match(str(key)):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid field name '{key}' — operator-like keys are not allowed.",
                )
            check_nosql_injection(value, f"{_path}.{key}")
    elif isinstance(data, list):
        for i, item in enumerate(data):
            check_nosql_injection(item, f"{_path}[{i}]")
    elif isinstance(data, str):
        if data.lower().strip() in _NOSQL_OPERATORS:
            raise HTTPException(
                status_code=400,
                detail=f"Forbidden value '{data}' at {_path}.",
            )
