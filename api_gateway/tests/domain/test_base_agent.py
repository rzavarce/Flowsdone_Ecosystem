"""Tests for the base agent's system prompt."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.domain.models.base_agent import BaseAgentSpec, build_system_prompt


def test_prompt_names_the_assistant_and_company_and_follows_the_tone():
    prompt = build_system_prompt(BaseAgentSpec(assistant_name="Fibi", company_name="Fibralan", tone="formal"))

    assert prompt.startswith("Eres Fibi, el asistente virtual de Fibralan.")
    assert "de usted" in prompt
    assert "Nunca inventes" in prompt
    assert "Sobre el negocio" not in prompt  # no instructions given


def test_instructions_are_included_and_braces_neutralized():
    prompt = build_system_prompt(BaseAgentSpec(
        assistant_name="Fibi {x}", company_name="Fibralan", instructions="  Horario {9-18} L-V  ",
    ))

    assert "{" not in prompt and "}" not in prompt
    assert "Fibi (x)" in prompt
    assert prompt.endswith("Sobre el negocio y cómo atender:\nHorario (9-18) L-V")


def test_validation():
    with pytest.raises(ValidationError):
        BaseAgentSpec(assistant_name="", company_name="X")
    with pytest.raises(ValidationError):
        BaseAgentSpec(assistant_name="A", company_name="X", tone="gracioso")
