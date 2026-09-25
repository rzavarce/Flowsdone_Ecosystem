"""Tests for the Langflow stylesheet injection (run: pytest dockers/langflow/tests)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from inject_css import MARKER, inject  # noqa: E402

CSS = Path(__file__).resolve().parents[1] / "flowsdone-langflow.css"


def test_adds_the_stylesheet_at_the_end_of_head_once(tmp_path):
    page = tmp_path / "index.html"
    page.write_text("<html><head><title>Langflow</title></head><body></body></html>", encoding="utf-8")

    assert inject(page, "a{b:c}") is True
    assert inject(page, "a{b:c}") is False

    html = page.read_text(encoding="utf-8")
    assert html.count(MARKER) == 1
    assert f"{MARKER}<style>a{{b:c}}</style></head>" in html


def test_a_page_without_head_is_refused(tmp_path):
    page = tmp_path / "index.html"
    page.write_text("<html></html>", encoding="utf-8")
    with pytest.raises(ValueError):
        inject(page, "a{b:c}")


def test_the_stylesheet_targets_the_promos():
    css = CSS.read_text(encoding="utf-8")
    assert "get_started_progress_title" in css
    assert "header_right_section_wrapper" in css
    assert "button-store" in css
