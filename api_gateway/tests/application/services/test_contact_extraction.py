"""Tests for extract_contact_details: contact details in what a contact writes."""

from __future__ import annotations

import pytest

from app.application.services.contact_extraction import extract_contact_details


@pytest.mark.parametrize(
    "text, asked, expected",
    [
        ("mi correo es Ana.Perez@Gmail.com gracias", None, {"email": "ana.perez@gmail.com"}),
        ("Hola, me llamo ana maría y quiero una cita", None, {"name": "Ana María"}),
        ("Me llamo María de la Luz", None, {"name": "María de la Luz"}),
        ("Ana Pérez", "¿Cuál es tu nombre?", {"name": "Ana Pérez"}),
        ("Soy Ana, mi móvil es +34 600-112-233", "Dime tu nombre y teléfono", {"name": "Ana", "phone": "+34600112233"}),
        (
            "Roger Zavarce, roger@x.com, 612345678",
            "Necesito tu nombre, email y teléfono",
            {"name": "Roger Zavarce", "email": "roger@x.com", "phone": "612345678"},
        ),
        ("600 11 22 33", "¿Me das un teléfono de contacto?", {"phone": "600112233"}),
    ],
)
def test_details_are_found(text, asked, expected):
    assert extract_contact_details(text, asked) == expected


@pytest.mark.parametrize(
    "text, asked",
    [
        ("Sí, claro", "¿Cuál es tu nombre?"),  # not a name
        ("quiero saber precios", "¿Cómo te llamas?"),  # a sentence, not a name
        ("Roger", "¿En qué te puedo ayudar?"),  # a short reply, but no one asked for a name
        ("mi pedido es 123456789", "¿En qué te ayudo?"),  # a number no one asked for
        ("123", "¿Tu teléfono?"),  # too short for a phone
        ("", None),
    ],
)
def test_nothing_is_taken_when_it_is_not_clearly_a_detail(text, asked):
    assert extract_contact_details(text, asked) == {}
