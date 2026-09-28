"""Tests for GoogleCalendarAppointmentComponent in google_calendar_appointment.py.

Same isolation approach as the sibling test files: stubs `langflow.*` and
the Google client packages instead of importing the real ones, and swaps
the Calendar service for an in-memory fake. Focused on what the component
exists for: booking only free slots, business-hours rules, idempotent
retries and failures reported (not raised) to the Agent.

Run directly with:
    pytest volumes/langflow/components_tests/test_google_calendar_appointment.py
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path


class _FakeGoogleAuthError(Exception):
    """Stand-in for google.auth.exceptions.GoogleAuthError (e.g. RefreshError)."""


class _FakeHttpError(Exception):
    """Stand-in for googleapiclient.errors.HttpError."""

    def __init__(self, status):
        super().__init__(f"HTTP {status}")
        self.resp = types.SimpleNamespace(status=status)


def _install_stubs() -> None:
    """Register minimal stand-ins for the third-party symbols this module imports."""

    class Component:
        pass

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
    for name in ("IntInput", "Output", "SecretStrInput", "StrInput"):
        setattr(langflow_io, name, type(name, (_InputBase,), {}))
    langflow_schema = types.ModuleType("langflow.schema")
    langflow_schema.Data = Data

    google = types.ModuleType("google")
    google_auth = types.ModuleType("google.auth")
    google_auth_exceptions = types.ModuleType("google.auth.exceptions")
    google_auth_exceptions.GoogleAuthError = _FakeGoogleAuthError
    google_oauth2 = types.ModuleType("google.oauth2")
    service_account = types.ModuleType("google.oauth2.service_account")
    service_account.Credentials = types.SimpleNamespace(
        from_service_account_info=lambda info, scopes: ("credentials", info["client_email"], tuple(scopes))
    )
    google_oauth2.service_account = service_account
    googleapiclient = types.ModuleType("googleapiclient")
    discovery = types.ModuleType("googleapiclient.discovery")
    discovery.build = lambda *args, **kwargs: ("service", args, kwargs)
    errors = types.ModuleType("googleapiclient.errors")
    errors.HttpError = _FakeHttpError

    sys.modules.setdefault("langflow", langflow)
    sys.modules["langflow.custom"] = langflow_custom
    sys.modules["langflow.io"] = langflow_io
    sys.modules["langflow.schema"] = langflow_schema
    sys.modules["google"] = google
    sys.modules["google.auth"] = google_auth
    sys.modules["google.auth.exceptions"] = google_auth_exceptions
    sys.modules["google.oauth2"] = google_oauth2
    sys.modules["google.oauth2.service_account"] = service_account
    sys.modules["googleapiclient"] = googleapiclient
    sys.modules["googleapiclient.discovery"] = discovery
    sys.modules["googleapiclient.errors"] = errors


_install_stubs()

_MODULE_PATH = Path(__file__).parent.parent / "components" / "google_calendar_appointment.py"
_spec = importlib.util.spec_from_file_location("google_calendar_appointment", _MODULE_PATH)
google_calendar_appointment = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(google_calendar_appointment)

GoogleCalendarAppointmentComponent = google_calendar_appointment.GoogleCalendarAppointmentComponent

# 2030-01-07 is a Monday, far enough in the future for the "already past" check.
_MONDAY = "2030-01-07"
_CALENDAR = "agenda@example.com"


class _Call:
    """Mimics a googleapiclient request object: runs `fn` on .execute()."""

    def __init__(self, fn):
        self._fn = fn

    def execute(self):
        return self._fn()


class _FakeCalendarService:
    """In-memory Calendar v3: events by id plus scripted free/busy answers."""

    def __init__(self, busy=None, freebusy_errors=None, insert_error=None, raise_on_call=None):
        self.events_by_id = {}
        self.raise_on_call = raise_on_call
        self.busy = busy or []
        self.freebusy_errors = freebusy_errors
        self.insert_error = insert_error
        self.inserted = []
        self.updated = []
        self.freebusy_bodies = []

    def events(self):
        service = self

        class _Events:
            def get(self, calendarId, eventId):
                def run():
                    if service.raise_on_call:
                        raise service.raise_on_call
                    if eventId not in service.events_by_id:
                        raise _FakeHttpError(404)
                    return service.events_by_id[eventId]

                return _Call(run)

            def insert(self, calendarId, body):
                def run():
                    if service.insert_error:
                        raise _FakeHttpError(service.insert_error)
                    event = {**body, "htmlLink": f"https://calendar.google.com/event?eid={body['id']}"}
                    service.events_by_id[body["id"]] = event
                    service.inserted.append(body)
                    return event

                return _Call(run)

            def update(self, calendarId, eventId, body):
                def run():
                    event = {**body, "htmlLink": "link"}
                    service.events_by_id[eventId] = event
                    service.updated.append(body)
                    return event

                return _Call(run)

        return _Events()

    def freebusy(self):
        service = self

        class _FreeBusy:
            def query(self, body):
                def run():
                    service.freebusy_bodies.append(body)
                    calendar = {"busy": service.busy}
                    if service.freebusy_errors:
                        calendar["errors"] = service.freebusy_errors
                    return {"calendars": {_CALENDAR: calendar}}

                return _Call(run)

        return _FreeBusy()


def _make_component(service=None, **overrides):
    component = GoogleCalendarAppointmentComponent()
    component.service_account_json = json.dumps({"client_email": "bot@proj.iam.gserviceaccount.com"})
    component.calendar_id = _CALENDAR
    component.timezone = "Europe/Madrid"
    component.default_duration_minutes = 30
    component.business_hours = ""
    component.business_days = ""
    component.title_template = "Cita: {customer_name}"
    component.start_datetime = f"{_MONDAY}T10:00"
    component.duration_minutes = 0
    component.customer_name = "Ana Pérez"
    component.customer_contact = "+34600111222"
    component.reason = "Demo del producto"
    for key, value in overrides.items():
        setattr(component, key, value)
    fake = service or _FakeCalendarService()
    component._build_service = lambda: fake
    return component, fake


def _run(component):
    return asyncio.run(component.create_appointment()).data


def test_books_free_slot_with_default_duration_and_customer_details():
    component, fake = _make_component()

    result = _run(component)

    assert result["success"] is True
    assert result["already_existed"] is False
    assert result["start"] == f"{_MONDAY}T10:00:00+01:00"
    assert result["end"] == f"{_MONDAY}T10:30:00+01:00"
    body = fake.inserted[0]
    assert body["summary"] == "Cita: Ana Pérez"
    assert "Contacto: +34600111222" in body["description"]
    assert "Motivo: Demo del producto" in body["description"]
    assert body["start"]["timeZone"] == "Europe/Madrid"


def test_uses_requested_duration_over_default():
    component, _ = _make_component(duration_minutes=60)

    result = _run(component)

    assert result["end"] == f"{_MONDAY}T11:00:00+01:00"


def test_busy_slot_is_not_booked_and_returns_day_busy_slots():
    # 09:15Z-09:45Z = 10:15-10:45 in Madrid: overlaps the 10:00-10:30 appointment.
    busy = [{"start": f"{_MONDAY}T09:15:00Z", "end": f"{_MONDAY}T09:45:00Z"}]
    component, fake = _make_component(service=_FakeCalendarService(busy=busy))

    result = _run(component)

    assert result["success"] is False
    assert "ocupado" in result["error"]
    assert result["busy"] == ["10:15-10:45"]
    assert fake.inserted == []


def test_adjacent_busy_slot_does_not_block():
    # 09:30Z-10:00Z = 10:30-11:00 in Madrid: starts exactly when the 10:00-10:30 appointment ends.
    busy = [{"start": f"{_MONDAY}T09:30:00Z", "end": f"{_MONDAY}T10:00:00Z"}]
    component, fake = _make_component(service=_FakeCalendarService(busy=busy))

    result = _run(component)

    assert result["success"] is True
    assert len(fake.inserted) == 1


def test_freebusy_queries_the_whole_local_day():
    component, fake = _make_component()

    _run(component)

    body = fake.freebusy_bodies[0]
    assert body["timeMin"] == f"{_MONDAY}T00:00:00+01:00"
    assert body["timeMax"] == "2030-01-08T00:00:00+01:00"
    assert body["items"] == [{"id": _CALENDAR}]


def test_retry_of_same_appointment_returns_existing_event():
    component, fake = _make_component()
    first = _run(component)

    second = _run(component)

    assert second["success"] is True
    assert second["already_existed"] is True
    assert second["event_id"] == first["event_id"]
    assert len(fake.inserted) == 1


def test_cancelled_event_with_same_id_is_revived_with_update():
    component, fake = _make_component()
    first = _run(component)
    fake.events_by_id[first["event_id"]]["status"] = "cancelled"

    result = _run(component)

    assert result["success"] is True
    assert result["already_existed"] is False
    assert len(fake.updated) == 1
    assert fake.updated[0]["status"] == "confirmed"


def test_different_customer_same_time_gets_different_event_id():
    component_a, _ = _make_component()
    component_b, _ = _make_component(customer_name="Luis Gómez")

    assert _run(component_a)["event_id"] != _run(component_b)["event_id"]


def test_event_id_uses_only_base32hex_characters():
    component, _ = _make_component()

    event_id = _run(component)["event_id"]

    assert set(event_id) <= set("0123456789abcdefghijklmnopqrstuv")
    assert len(event_id) >= 5


def test_explicit_offset_is_converted_to_calendar_time_zone():
    component, _ = _make_component(start_datetime=f"{_MONDAY}T09:00:00+00:00")

    result = _run(component)

    assert result["start"] == f"{_MONDAY}T10:00:00+01:00"


def test_invalid_start_is_reported_not_raised():
    component, fake = _make_component(start_datetime="el lunes a las 10")

    result = _run(component)

    assert result["success"] is False
    assert "YYYY-MM-DDTHH:MM" in result["error"]
    assert fake.inserted == []


def test_past_start_is_rejected():
    component, _ = _make_component(start_datetime="2020-01-06T10:00")

    result = _run(component)

    assert result["success"] is False
    assert "ya pasó" in result["error"]


def test_missing_customer_name_is_rejected():
    component, _ = _make_component(customer_name="  ")

    result = _run(component)

    assert result["success"] is False
    assert "nombre" in result["error"]


def test_outside_business_hours_is_rejected():
    component, fake = _make_component(business_hours="09:00-18:00", start_datetime=f"{_MONDAY}T17:45")

    result = _run(component)

    assert result["success"] is False
    assert "09:00-18:00" in result["error"]
    assert fake.freebusy_bodies == []


def test_inside_business_hours_is_accepted():
    component, _ = _make_component(business_hours="09:00-18:00", start_datetime=f"{_MONDAY}T17:30")

    assert _run(component)["success"] is True


def test_non_business_day_is_rejected():
    component, _ = _make_component(business_days="1,2,3,4,5", start_datetime="2030-01-12T10:00")  # Saturday

    result = _run(component)

    assert result["success"] is False
    assert "día" in result["error"]


def test_invalid_business_hours_config_is_reported():
    component, _ = _make_component(business_hours="de 9 a 6")

    result = _run(component)

    assert result["success"] is False
    assert "Horario de citas" in result["error"]


def test_invalid_timezone_is_reported():
    component, _ = _make_component(timezone="Madrid")

    result = _run(component)

    assert result["success"] is False
    assert "Zona horaria" in result["error"]


def test_calendar_not_shared_explains_how_to_fix():
    component, _ = _make_component(service=_FakeCalendarService(insert_error=403))

    result = _run(component)

    assert result["success"] is False
    assert "compartido" in result["error"]


def test_freebusy_calendar_error_is_reported():
    service = _FakeCalendarService(freebusy_errors=[{"domain": "global", "reason": "notFound"}])
    component, fake = _make_component(service=service)

    result = _run(component)

    assert result["success"] is False
    assert "notFound" in result["error"]
    assert fake.inserted == []


def test_title_template_with_unknown_placeholder_falls_back():
    component, fake = _make_component(title_template="Cita {cliente}")

    _run(component)

    assert fake.inserted[0]["summary"] == "Cita: Ana Pérez"


def test_invalid_service_account_json_is_reported():
    component = GoogleCalendarAppointmentComponent()
    component.service_account_json = "no es json"

    try:
        component._build_service()
    except google_calendar_appointment.BookingError as exc:
        assert "JSON" in str(exc)
    else:
        raise AssertionError("expected BookingError")


def test_build_service_uses_calendar_scope():
    component = GoogleCalendarAppointmentComponent()
    component.service_account_json = json.dumps({"client_email": "bot@proj.iam.gserviceaccount.com"})

    service = component._build_service()

    _, args, kwargs = service
    assert args == ("calendar", "v3")
    assert kwargs["credentials"][2] == ("https://www.googleapis.com/auth/calendar",)


def test_rejected_credential_is_reported_not_raised():
    error = _FakeGoogleAuthError("invalid_grant: account not found")
    component, fake = _make_component(service=_FakeCalendarService(raise_on_call=error))

    result = _run(component)

    assert result["success"] is False
    assert "invalid_grant" in result["error"]
    assert fake.inserted == []


def test_network_failure_is_reported_not_raised():
    component, _ = _make_component(service=_FakeCalendarService(raise_on_call=ConnectionError("timed out")))

    result = _run(component)

    assert result["success"] is False
    assert "No se pudo conectar" in result["error"]
