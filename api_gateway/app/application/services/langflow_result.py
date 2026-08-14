"""Shared helper for extracting a human-readable response from a raw
Langflow execution result.
"""

from __future__ import annotations

from typing import Any, Optional


def extract_text_from_langflow_result(value: Any) -> Optional[str]:
    """Recursively extract a human-readable response string.

    Walks common Langflow response shapes (dicts with a
    message/response/output/... key, lists, nested errors) to find the
    first non-empty text value. Used by both the text-channel outbound
    handler and the voice worker, which share the same Langflow
    response shapes but otherwise deliver the result differently.

    Args:
        value (Any): A Langflow result, or a nested part of one.

    Returns:
        Optional[str]: The extracted text, or None if no text could be
        found.
    """
    if value is None:
        return None

    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None

    if isinstance(value, dict):
        for key in ("message", "response", "output", "content", "text", "answer", "result"):
            if key in value:
                extracted = extract_text_from_langflow_result(value[key])
                if extracted:
                    return extracted

        for key in ("detail", "error"):
            if key in value:
                extracted = extract_text_from_langflow_result(value[key])
                if extracted:
                    return extracted

        for key in ("outputs", "data", "results"):
            if key in value:
                extracted = extract_text_from_langflow_result(value[key])
                if extracted:
                    return extracted

        return None

    if isinstance(value, list):
        for item in value:
            extracted = extract_text_from_langflow_result(item)
            if extracted:
                return extracted

    return None
