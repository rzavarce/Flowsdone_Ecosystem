"""Find a contact's details in what they write (or say) to the agent.

Rule-based, no LLM: it runs on every inbound message, for free.

- An email is taken from any message: it's unambiguous.
- A phone number or a name only when the agent's previous message asked
  for it ("¿me das tu teléfono?", "¿cómo te llamas?"), because a bare
  number may be an order id and a short reply may be anything else.
- "Me llamo Ana", "mi nombre es Ana Pérez" are taken without being asked.

What is found only fills fields the card doesn't have yet (see
ManageConversationContactsUseCase.record_from_channel).
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
# Digits with the usual separators; validated by digit count afterwards.
_PHONE = re.compile(r"\+?\d[\d\s().-]{7,20}\d")
_ASKED_PHONE = re.compile(r"tel[eé]fono|m[oó]vil|celular|n[uú]mero de contacto|whatsapp|phone|telèfon|mòbil", re.I)
_ASKED_NAME = re.compile(r"\bnombre\b|c[oó]mo te llamas|c[oó]mo se llama|\bname\b|\bnom\b|com et dius", re.I)
_SAYS_NAME = re.compile(
    r"\b(?:me llamo|mi nombre es|my name is|em dic|el meu nom és)\s+(?P<name>[^\W\d_][^\W\d_'’ -]*(?:[ '’-][^\W\d_][^\W\d_'’-]*){0,3})",
    re.I,
)
# Common words that are never part of a name: a reply containing one is a
# sentence ("quiero saber precios"), and after "me llamo" they end the name
# ("me llamo Ana y quiero una cita").
_NOT_A_NAME = set(
    """
    si sí no vale ok okay claro hola gracias bueno perfecto acuerdo buenas buenos días dias tardes noches
    y e o u and or i que qué quiero quería queria necesito busco tengo tenía quisiera puedo puedes
    para pero con por porque sobre saber precio precios cita citas información informacion info ayuda
    un una unos unas el lo al en a mi mis tu su sus me te se es soy estoy era
    yes hello hi hey thanks want need would like please my is the an
    vull voldria necessito tinc per amb però perquè
    """.split()
)
# Particles allowed inside a name ("María de la Luz"), never first or last.
_NAME_PARTICLES = {"de", "del", "la", "las", "los", "da", "do", "dos", "van", "von"}
_MAX_NAME_WORDS = 4


def _phone(text: str) -> Optional[str]:
    """First phone-like number in a text.

    Args:
        text (str): The message.

    Returns:
        Optional[str]: The number with only digits (and a leading "+"), or
        None if there is no 9-15 digit number.
    """
    for match in _PHONE.finditer(text):
        raw = match.group(0)
        digits = re.sub(r"\D", "", raw)
        if 9 <= len(digits) <= 15:
            return ("+" if raw.startswith("+") else "") + digits
    return None


def _name(words: List[str], *, whole: bool) -> Optional[str]:
    """The name at the start of some words.

    Args:
        words (List[str]): Words, in order.
        whole (bool): All the words must be the name (a reply to "¿cómo te
            llamas?"); otherwise the name ends at the first common word
            (after "me llamo").

    Returns:
        Optional[str]: The name, capitalised, or None.
    """
    name: List[str] = []
    for word in words:
        lower = word.lower()
        if not re.fullmatch(r"[^\W\d_]+(?:['’-][^\W\d_]+)*", word):
            return None
        if lower in _NOT_A_NAME or (lower in _NAME_PARTICLES and not name):
            if whole:
                return None
            break
        name.append(word)
    while name and name[-1].lower() in _NAME_PARTICLES:
        name.pop()
    if not name or len(name) > _MAX_NAME_WORDS:
        return None
    return " ".join(w if w.lower() in _NAME_PARTICLES else w[:1].upper() + w[1:] for w in name)


def _name_reply(text: str) -> Optional[str]:
    """A reply that is just a name ("Ana Pérez", "Soy Ana", "Ana, gracias").

    Args:
        text (str): The message.

    Returns:
        Optional[str]: The name, or None if the reply doesn't look like one.
    """
    reply = re.sub(r"^(?:soy|es|me llamo|mi nombre es|i am|i'm|sóc)\s+", "", text.strip(), flags=re.I)
    reply = re.split(r"[,.;:!?\n]", reply, maxsplit=1)[0]
    return _name(reply.split(), whole=True)


def extract_contact_details(text: str, asked: Optional[str] = None) -> Dict[str, str]:
    """Contact details in one inbound message.

    Args:
        text (str): What the contact wrote or said.
        asked (Optional[str]): The agent's previous message, if any: what it
            asked for decides how a bare number or short reply is read.

    Returns:
        Dict[str, str]: Any of "name", "email", "phone" found.
    """
    found: Dict[str, str] = {}
    if not text:
        return found
    email = _EMAIL.search(text)
    if email:
        found["email"] = email.group(0).lower()
    rest = _EMAIL.sub(" ", text)

    said = _SAYS_NAME.search(rest)
    if said:
        name = _name(said.group("name").split(), whole=False)
        if name:
            found["name"] = name
    asked = asked or ""
    if "name" not in found and _ASKED_NAME.search(asked):
        name = _name_reply(rest)
        if name:
            found["name"] = name
    if _ASKED_PHONE.search(asked):
        phone = _phone(rest)
        if phone:
            found["phone"] = phone
    return found
