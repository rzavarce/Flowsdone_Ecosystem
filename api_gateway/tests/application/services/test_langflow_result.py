"""Tests for extract_text_from_langflow_result."""

from __future__ import annotations

import pytest

from api_gateway.app.application.services.langflow_result import (
    extract_text_from_langflow_result,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("plain string", "plain string"),
        ("   ", None),
        (None, None),
        ({"message": "hi"}, "hi"),
        ({"response": "hi"}, "hi"),
        ({"output": {"message": "nested"}}, "nested"),
        ({"outputs": [{"content": "deep"}]}, "deep"),
        ({"data": {"results": [{"text": "very deep"}]}}, "very deep"),
        ({"detail": "an error"}, "an error"),
        ([{"message": ""}, {"message": "second wins"}], "second wins"),
        ({"unrelated": "nope"}, None),
        ([], None),
    ],
)
def test_extract_text_handles_common_langflow_shapes(value, expected):
    assert extract_text_from_langflow_result(value) == expected
