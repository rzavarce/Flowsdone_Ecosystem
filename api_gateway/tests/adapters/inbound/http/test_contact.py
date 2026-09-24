"""HTTP tests for the public contact endpoint (POST /public/contact)."""

from __future__ import annotations

import pytest

from app.adapters.inbound.http.contact import router
from app.application.use_cases.send_contact_request import SendContactRequestUseCase
from app.domain.ports.outbound import EmailSendError
from api_gateway.tests.support.asgi import client_for_router
from api_gateway.tests.support.fakes import FakeEmailSender, FakeLoginThrottle

pytestmark = pytest.mark.anyio

FORM = {"name": "Ana", "email": "ana@tienda.es", "interest": "plans", "message": "¿Qué plan me conviene?"}


def _use_case(email=None, recipient="team@flowsdone.com"):
    return SendContactRequestUseCase(
        email_sender=email or FakeEmailSender(), throttle=FakeLoginThrottle(), recipient=recipient,
        max_per_ip=1, window_seconds=3600,
    )


async def _post(use_case, body):
    async with client_for_router(router, send_contact_request_use_case=use_case) as client:
        return await client.post("/public/contact", json=body)


async def test_a_valid_request_is_emailed():
    email = FakeEmailSender()
    response = await _post(_use_case(email), FORM)
    assert response.status_code == 204 and len(email.sent) == 1


async def test_the_honeypot_is_accepted_and_dropped():
    email = FakeEmailSender()
    response = await _post(_use_case(email), {**FORM, "website": "http://spam"})
    assert response.status_code == 204 and email.sent == []


async def test_errors_map_to_http():
    use_case = _use_case()
    async with client_for_router(router, send_contact_request_use_case=use_case) as client:
        first = await client.post("/public/contact", json=FORM)
        second = await client.post("/public/contact", json=FORM)
    assert first.status_code == 204 and second.status_code == 429 and second.headers["retry-after"] == "3600"

    assert (await _post(_use_case(recipient=None), FORM)).status_code == 503
    assert (await _post(_use_case(), {**FORM, "email": "x"})).status_code == 422

    class Failing(FakeEmailSender):
        async def send_template(self, **kwargs):
            raise EmailSendError("down")

    assert (await _post(_use_case(Failing()), FORM)).status_code == 502
