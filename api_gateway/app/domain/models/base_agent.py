"""The base agent created by the new-client wizard: what it is told about
the business, and the system prompt built from it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AgentTone = Literal["cercano", "profesional", "formal"]

_TONES = {
    "cercano": "Habla de forma cercana y amable, tuteando al cliente, sin perder la profesionalidad.",
    "profesional": "Habla de forma profesional y clara, con un trato cordial.",
    "formal": "Habla de forma formal, tratando al cliente de usted.",
}


class BaseAgentSpec(BaseModel):
    """What the wizard asks to set up a tenant's first agent.

    Attributes:
        assistant_name (str): Name the assistant introduces itself with.
        company_name (str): The client's business.
        tone (AgentTone): How it talks to customers.
        instructions (str): Free text about the business: what it does,
            opening hours, what the assistant should and shouldn't do.
    """

    assistant_name: str = Field(min_length=1, max_length=60)
    company_name: str = Field(min_length=1, max_length=200)
    tone: AgentTone = "cercano"
    instructions: str = Field(default="", max_length=4000)


def _plain(text: str) -> str:
    """Neutralize braces: prompt templates treat `{name}` as a variable,
    so user text must never introduce one.

    Args:
        text (str): Text typed by a person.

    Returns:
        str: The text with `{`/`}` turned into parentheses, trimmed.
    """
    return text.replace("{", "(").replace("}", ")").strip()


def build_system_prompt(spec: BaseAgentSpec) -> str:
    """The base agent's system prompt (Spanish, chat-channel oriented).

    Args:
        spec (BaseAgentSpec): What the wizard collected.

    Returns:
        str: The prompt, free of template variables.
    """
    parts = [
        f"Eres {_plain(spec.assistant_name)}, el asistente virtual de {_plain(spec.company_name)}.",
        _TONES[spec.tone],
        "Respondes por canales de mensajería (WhatsApp, Telegram…): mensajes breves y claros, "
        "sin formato Markdown, en el idioma en que te escriba el cliente.",
        "Si no sabes algo o te piden algo que no puedes hacer, dilo con sinceridad y ofrece que "
        "una persona del equipo le contacte. Nunca inventes precios, horarios ni datos.",
    ]
    instructions = _plain(spec.instructions)
    if instructions:
        parts.append(f"Sobre el negocio y cómo atender:\n{instructions}")
    return "\n\n".join(parts)
