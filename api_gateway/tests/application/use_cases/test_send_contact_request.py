"""Tests for SendContactRequestUseCase."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.application.use_cases.send_contact_request import (
    ContactNotConfiguredError,
    SendContactRequestUseCase,
    TooManyContactRequestsError,
)
from app.domain.models.contact import ContactRequest
from api_gateway.tests.support.fakes import FakeEmailSender, FakeLoginThrottle

pytestmark = pytest.mark.anyio


def _request(**over):
    data = dict(name="  Ana López ", email="Ana@Tienda.es", company="Tienda Aurora", phone="",
                interest="voice", message="Queremos un asistente para el teléfono.")
    data.update(over)
    return ContactRequest(**data)


def _use_case(recipient="team@flowsdone.com", max_per_ip=2):
    email, throttle = FakeEmailSender(), FakeLoginThrottle()
    use_case = SendContactRequestUseCase(
        email_sender=email, throttle=throttle, recipient=recipient, max_per_ip=max_per_ip, window_seconds=3600
    )
    return use_case, email, throttle


async def test_emails_the_team_with_replies_to_the_prospect():
    use_case, email, throttle = _use_case()

    await use_case.execute(_request(), client_ip="1.2.3.4")

    [sent] = email.sent
    assert sent["to"] == "team@flowsdone.com" and sent["template"] == "contact_request"
    assert sent["reply_to"] == "ana@tienda.es"
    assert sent["subject"] == "Nuevo contacto desde la web: Ana López (Tienda Aurora)"
    assert sent["context"]["interest_label"] == "Asistente telefónico de voz"
    assert sent["context"]["phone"] is None  # blank optional fields are dropped
    assert throttle.windows == {"contact:ip:1.2.3.4": 3600}


async def test_the_subject_never_carries_line_breaks():
    use_case, email, _ = _use_case()
    await use_case.execute(_request(name="Ana\r\nBcc: x@y.com", company=None), client_ip="1.2.3.4")
    assert "\n" not in email.sent[0]["subject"] and "\r" not in email.sent[0]["subject"]


async def test_each_ip_is_limited():
    use_case, email, _ = _use_case(max_per_ip=2)
    await use_case.execute(_request(), client_ip="1.2.3.4")
    await use_case.execute(_request(), client_ip="1.2.3.4")

    with pytest.raises(TooManyContactRequestsError):
        await use_case.execute(_request(), client_ip="1.2.3.4")
    await use_case.execute(_request(), client_ip="5.6.7.8")  # another IP is fine
    assert len(email.sent) == 3


async def test_without_recipient_the_form_is_off():
    use_case, email, _ = _use_case(recipient=None)
    with pytest.raises(ContactNotConfiguredError):
        await use_case.execute(_request(), client_ip="1.2.3.4")
    assert email.sent == []


@pytest.mark.parametrize("over", [
    {"email": "no-es-un-email"}, {"name": " "}, {"message": "corto"}, {"interest": "hacking"},
])
def test_invalid_requests_are_rejected(over):
    with pytest.raises(ValidationError):
        _request(**over)
