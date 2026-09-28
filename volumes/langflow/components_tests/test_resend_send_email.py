"""Tests for ResendSendEmailComponent in resend_send_email.py.

Same isolation approach as the sibling test files: stubs `langflow.*` and
`httpx` instead of importing the real packages, and replays scripted
Resend responses. Focused on what the Agent can and can't control (one
recipient, fixed sender, escaped HTML), the .ics attachment, idempotency,
retries and the per-run cap.

Run directly with:
    pytest volumes/langflow/components_tests/test_resend_send_email.py
"""

from __future__ import annotations

import asyncio
import base64
import importlib.util
import sys
import types
from pathlib import Path


class _FakeRequestError(Exception):
    """Stand-in for httpx.RequestError (network-level failures)."""


class _FakeResponse:
    def __init__(self, status_code, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def json(self):
        if self._json_data is None:
            raise ValueError("no json body")
        return self._json_data


class _FakeAsyncClient:
    """Replays a scripted sequence of responses/exceptions, one per call to .post()."""

    next_script = []
    calls = []
    sleeps = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None, headers=None):
        type(self).calls.append({"url": url, "json": json, "headers": headers})
        step = type(self).next_script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


async def _fake_sleep(seconds):
    _FakeAsyncClient.sleeps.append(seconds)


def _install_stubs() -> None:
    """Register minimal stand-ins for the third-party symbols this module imports."""

    class Component:
        def set(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)
            return self

    class _InputBase:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class Data:
        def __init__(self, data=None, **kwargs):
            self.data = data if data is not None else kwargs

    langflow = types.ModuleType("langflow")
    langflow_custom = types.ModuleType("langflow.custom")
    langflow_custom.Component = Component
    langflow_io = types.ModuleType("langflow.io")
    for name in ("IntInput", "MultilineInput", "Output", "SecretStrInput", "StrInput"):
        setattr(langflow_io, name, type(name, (_InputBase,), {}))
    langflow_schema = types.ModuleType("langflow.schema")
    langflow_schema.Data = Data

    httpx_module = types.ModuleType("httpx")
    httpx_module.AsyncClient = _FakeAsyncClient
    httpx_module.RequestError = _FakeRequestError

    sys.modules.setdefault("langflow", langflow)
    sys.modules["langflow.custom"] = langflow_custom
    sys.modules["langflow.io"] = langflow_io
    sys.modules["langflow.schema"] = langflow_schema
    sys.modules["httpx"] = httpx_module


_install_stubs()

_MODULE_PATH = Path(__file__).parent.parent / "components" / "flowsdone" / "resend_send_email.py"
_spec = importlib.util.spec_from_file_location("resend_send_email", _MODULE_PATH)
resend_send_email = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(resend_send_email)
resend_send_email.asyncio.sleep = _fake_sleep

ResendSendEmailComponent = resend_send_email.ResendSendEmailComponent

_TOOL_ARGS = {
    "to_email": "ana@example.com",
    "subject": "Tu cita está confirmada",
    "body": "Hola Ana,\n\nTe esperamos el lunes a las 10:00.",
    "appointment_start": "",
    "appointment_duration_minutes": 0,
    "appointment_title": "",
}


def _reset():
    _FakeAsyncClient.next_script = []
    _FakeAsyncClient.calls = []
    _FakeAsyncClient.sleeps = []


def _make_component(**overrides):
    _reset()
    component = ResendSendEmailComponent()
    component.api_key = "re_test"
    component.from_email = "citas@mail.flowsdone.com"
    component.from_name = "Clínica Sonrisa vía Flowsdone"
    component.reply_to = "contacto@clinicasonrisa.com"
    component.bcc = ""
    component.footer = ""
    component.timezone = "Europe/Madrid"
    component.default_duration_minutes = 30
    component.max_emails_per_run = 2
    component.api_base_url = "https://api.resend.com"
    component.timeout = 15
    for key, value in {**_TOOL_ARGS, **overrides}.items():
        setattr(component, key, value)
    return component


def _run(component, **tool_args):
    """Runs the tool once; `tool_args` are set first, like the Agent's arguments on a later call."""
    component.set(**tool_args)
    return asyncio.run(component.send_email()).data


def _ok(email_id="email_123"):
    return _FakeResponse(200, json_data={"id": email_id})


def _ics_of(call):
    return base64.b64decode(call["json"]["attachments"][0]["content"]).decode("utf-8")


def test_sends_with_fixed_sender_reply_to_and_single_recipient():
    component = _make_component()
    _FakeAsyncClient.next_script = [_ok()]

    result = _run(component)

    assert result == {"success": True, "id": "email_123", "to": "ana@example.com", "calendar_attached": False}
    call = _FakeAsyncClient.calls[0]
    assert call["url"] == "https://api.resend.com/emails"
    assert call["headers"]["Authorization"] == "Bearer re_test"
    body = call["json"]
    assert body["from"] == '"Clínica Sonrisa vía Flowsdone" <citas@mail.flowsdone.com>'
    assert body["to"] == ["ana@example.com"]
    assert body["reply_to"] == "contacto@clinicasonrisa.com"
    assert "bcc" not in body
    assert "attachments" not in body
    assert body["text"] == _TOOL_ARGS["body"]


def test_html_escapes_markup_and_keeps_paragraphs_and_line_breaks():
    component = _make_component(body='Hola <b>Ana</b>\nlínea 2\n\n<script>alert(1)</script> & fin')
    _FakeAsyncClient.next_script = [_ok()]

    _run(component)

    rendered = _FakeAsyncClient.calls[0]["json"]["html"]
    assert "<b>" not in rendered and "<script>" not in rendered
    assert "Hola &lt;b&gt;Ana&lt;/b&gt;<br>línea 2</p><p>&lt;script&gt;" in rendered
    assert "&amp; fin" in rendered


def test_footer_and_bcc_from_canvas_are_added():
    component = _make_component(footer="Clínica Sonrisa\nTel. 910 000 000", bcc="copia@clinicasonrisa.com")
    _FakeAsyncClient.next_script = [_ok()]

    _run(component)

    body = _FakeAsyncClient.calls[0]["json"]
    assert body["bcc"] == ["copia@clinicasonrisa.com"]
    assert body["text"].endswith("\n\n--\nClínica Sonrisa\nTel. 910 000 000")
    assert "Tel. 910 000 000" in body["html"]


def test_sender_without_name_uses_bare_address():
    component = _make_component(from_name="")
    _FakeAsyncClient.next_script = [_ok()]

    _run(component)

    assert _FakeAsyncClient.calls[0]["json"]["from"] == "citas@mail.flowsdone.com"


def test_several_recipients_are_rejected():
    for value in ("ana@example.com, luis@example.com", "ana@example.com;luis@example.com", "Ana <ana@example.com>"):
        component = _make_component(to_email=value)

        result = _run(component)

        assert result["success"] is False, value
        assert "uno solo" in result["error"]
        assert _FakeAsyncClient.calls == []


def test_missing_subject_or_body_is_rejected():
    for override, word in (({"subject": "  "}, "asunto"), ({"body": ""}, "cuerpo")):
        component = _make_component(**override)

        result = _run(component)

        assert result["success"] is False
        assert word in result["error"]


def test_appointment_start_attaches_ics_in_utc():
    component = _make_component(appointment_start="2030-01-07T10:00", appointment_title="Cita en Clínica Sonrisa")
    _FakeAsyncClient.next_script = [_ok()]

    result = _run(component)

    assert result["calendar_attached"] is True
    attachment = _FakeAsyncClient.calls[0]["json"]["attachments"][0]
    assert attachment["filename"] == "cita.ics"
    assert attachment["content_type"].startswith("text/calendar")
    ics = _ics_of(_FakeAsyncClient.calls[0])
    assert "DTSTART:20300107T090000Z\r\n" in ics
    assert "DTEND:20300107T093000Z\r\n" in ics
    assert "SUMMARY:Cita en Clínica Sonrisa\r\n" in ics
    assert "ORGANIZER;CN=\"Clínica Sonrisa vía Flowsdone\":mailto:citas@mail.flowsdone.com\r\n" in ics.replace("\r\n ", "")
    assert ics.startswith("BEGIN:VCALENDAR\r\n") and ics.endswith("END:VCALENDAR\r\n")


def test_ics_uses_requested_duration_and_subject_as_default_title():
    component = _make_component(appointment_start="2030-07-07T10:00", appointment_duration_minutes=60)
    _FakeAsyncClient.next_script = [_ok()]

    _run(component)

    ics = _ics_of(_FakeAsyncClient.calls[0])
    # July: Madrid is UTC+2.
    assert "DTSTART:20300707T080000Z" in ics
    assert "DTEND:20300707T090000Z" in ics
    assert "SUMMARY:Tu cita está confirmada" in ics


def test_ics_escapes_text_and_folds_long_lines():
    component = _make_component(appointment_start="2030-01-07T10:00", body="Trae: DNI, tarjeta; y receta\n" + "x" * 200)
    _FakeAsyncClient.next_script = [_ok()]

    _run(component)

    ics = _ics_of(_FakeAsyncClient.calls[0])
    unfolded = ics.replace("\r\n ", "")
    assert "DESCRIPTION:Trae: DNI\\, tarjeta\\; y receta\\n" in unfolded
    assert all(len(line.encode("utf-8")) <= 75 for line in ics.split("\r\n"))


def test_same_appointment_keeps_the_same_ics_uid():
    uids = []
    for body in ("Primera confirmación", "Confirmación corregida"):
        component = _make_component(appointment_start="2030-01-07T10:00", body=body)
        _FakeAsyncClient.next_script = [_ok()]
        _run(component)
        ics = _ics_of(_FakeAsyncClient.calls[0])
        uids.append(next(line for line in ics.split("\r\n") if line.startswith("UID:")))

    assert uids[0] == uids[1]


def test_invalid_appointment_start_is_reported_and_nothing_sent():
    component = _make_component(appointment_start="lunes 10h")

    result = _run(component)

    assert result["success"] is False
    assert "YYYY-MM-DDTHH:MM" in result["error"]
    assert _FakeAsyncClient.calls == []


def test_idempotency_key_is_stable_for_same_email_and_differs_otherwise():
    keys = []
    for subject in ("Asunto A", "Asunto A", "Asunto B"):
        component = _make_component(subject=subject)
        _FakeAsyncClient.next_script = [_ok()]
        _run(component)
        keys.append(_FakeAsyncClient.calls[0]["headers"]["Idempotency-Key"])

    assert keys[0] == keys[1] != keys[2]
    assert keys[0].startswith("flowsdone-")


def test_retries_rate_limit_then_succeeds_with_same_idempotency_key():
    component = _make_component()
    _FakeAsyncClient.next_script = [_FakeResponse(429, json_data={"message": "Too many requests"}), _ok()]

    result = _run(component)

    assert result["success"] is True
    assert len(_FakeAsyncClient.calls) == 2
    assert _FakeAsyncClient.calls[0]["headers"]["Idempotency-Key"] == _FakeAsyncClient.calls[1]["headers"]["Idempotency-Key"]
    assert _FakeAsyncClient.sleeps == [0.5]


def test_network_error_is_retried_and_finally_reported():
    component = _make_component()
    _FakeAsyncClient.next_script = [_FakeRequestError("timeout")] * 3

    result = _run(component)

    assert result["success"] is False
    assert "No se pudo conectar con Resend" in result["error"]
    assert len(_FakeAsyncClient.calls) == 3


def test_validation_error_from_resend_is_not_retried():
    component = _make_component()
    _FakeAsyncClient.next_script = [_FakeResponse(422, json_data={"message": "Invalid `to` field."})]

    result = _run(component)

    assert result["success"] is False
    assert "422" in result["error"] and "Invalid `to` field." in result["error"]
    assert len(_FakeAsyncClient.calls) == 1


def test_bad_api_key_or_unverified_sender_is_explained():
    component = _make_component()
    _FakeAsyncClient.next_script = [_FakeResponse(403, json_data={"message": "The domain is not verified."})]

    result = _run(component)

    assert result["success"] is False
    assert "API key o el remitente" in result["error"]
    assert "not verified" in result["error"]


def test_per_run_cap_stops_further_sends():
    component = _make_component(max_emails_per_run=2)
    _FakeAsyncClient.next_script = [_ok("e1"), _ok("e2")]

    first = _run(component)
    second = _run(component, **{**_TOOL_ARGS, "subject": "Otro"})
    third = _run(component, **{**_TOOL_ARGS, "subject": "Y otro más"})

    assert first["success"] and second["success"]
    assert third["success"] is False
    assert "no se envían más" in third["error"]
    assert len(_FakeAsyncClient.calls) == 2


def test_failed_send_does_not_count_towards_the_cap():
    component = _make_component(max_emails_per_run=1)
    _FakeAsyncClient.next_script = [_FakeResponse(422, json_data={"message": "bad"}), _ok()]

    _run(component)
    result = _run(component, **_TOOL_ARGS)

    assert result["success"] is True


def test_arguments_of_a_previous_call_do_not_leak_into_the_next():
    component = _make_component(appointment_start="2030-01-07T10:00")
    _FakeAsyncClient.next_script = [_ok(), _ok()]
    _run(component)
    args = {k: v for k, v in _TOOL_ARGS.items() if not k.startswith("appointment")}

    result = _run(component, **{**args, "subject": "Recordatorio sin cita"})

    assert result["calendar_attached"] is False
    assert "attachments" not in _FakeAsyncClient.calls[1]["json"]
    assert component.to_email == ""
