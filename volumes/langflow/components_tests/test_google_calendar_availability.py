"""Tests for GoogleCalendarAvailabilityComponent in google_calendar_availability.py.

Same isolation approach as the sibling test files: stubs `langflow.*` and
the Google client packages instead of importing the real ones, and swaps
the Calendar service for a fake that answers free/busy. Focused on the
slot arithmetic (busy gaps, grid, business hours, "today" cut-off) and on
failures being reported to the Agent instead of raised.

Run directly with:
    pytest volumes/langflow/components_tests/test_google_calendar_availability.py
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
from datetime import datetime as real_datetime
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

_MODULE_PATH = Path(__file__).parent.parent / "components" / "google_calendar_availability.py"
_spec = importlib.util.spec_from_file_location("google_calendar_availability", _MODULE_PATH)
google_calendar_availability = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(google_calendar_availability)

GoogleCalendarAvailabilityComponent = google_calendar_availability.GoogleCalendarAvailabilityComponent

# 2030-01-07 is a Monday; Madrid is UTC+1 in January.
_MONDAY = "2030-01-07"
_CALENDAR = "agenda@example.com"


class _Call:
    """Mimics a googleapiclient request object: runs `fn` on .execute()."""

    def __init__(self, fn):
        self._fn = fn

    def execute(self):
        return self._fn()


class _FakeCalendarService:
    """Answers free/busy with scripted busy slots (UTC strings, like Google)."""

    def __init__(self, busy=None, errors=None, raise_on_call=None):
        self.busy = busy or []
        self.errors = errors
        self.raise_on_call = raise_on_call
        self.queries = []

    def freebusy(self):
        service = self

        class _FreeBusy:
            def query(self, body):
                def run():
                    if service.raise_on_call:
                        raise service.raise_on_call
                    service.queries.append(body)
                    calendar = {"busy": service.busy}
                    if service.errors:
                        calendar["errors"] = service.errors
                    return {"calendars": {_CALENDAR: calendar}}

                return _Call(run)

        return _FreeBusy()


def _busy(start_local, end_local):
    """Busy slot on _MONDAY given in Madrid local 'HH:MM', returned as Google's UTC strings."""
    to_utc = lambda hhmm: f"{_MONDAY}T{int(hhmm[:2]) - 1:02d}:{hhmm[3:]}:00Z"  # noqa: E731
    return {"start": to_utc(start_local), "end": to_utc(end_local)}


def _make_component(service=None, **overrides):
    component = GoogleCalendarAvailabilityComponent()
    component.service_account_json = json.dumps({"client_email": "bot@proj.iam.gserviceaccount.com"})
    component.calendar_id = _CALENDAR
    component.timezone = "Europe/Madrid"
    component.business_hours = "09:00-12:00"
    component.business_days = "1,2,3,4,5"
    component.default_duration_minutes = 30
    component.slot_step_minutes = 30
    component.date = _MONDAY
    component.duration_minutes = 0
    for key, value in overrides.items():
        setattr(component, key, value)
    fake = service or _FakeCalendarService()
    component._build_service = lambda: fake
    return component, fake


def _run(component):
    return asyncio.run(component.check_availability()).data


def test_empty_day_offers_every_slot_in_business_hours():
    component, _ = _make_component()

    result = _run(component)

    assert result["success"] is True
    assert result["free_ranges"] == ["09:00-12:00"]
    assert result["available_starts"] == ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30"]
    assert result["timezone"] == "Europe/Madrid"
    assert result["duration_minutes"] == 30


def test_busy_slots_are_carved_out():
    component, _ = _make_component(service=_FakeCalendarService(busy=[_busy("10:00", "11:00")]))

    result = _run(component)

    assert result["free_ranges"] == ["09:00-10:00", "11:00-12:00"]
    assert result["available_starts"] == ["09:00", "09:30", "11:00", "11:30"]


def test_longer_duration_only_offers_starts_where_it_fits():
    component, _ = _make_component(
        service=_FakeCalendarService(busy=[_busy("10:00", "10:30")]), duration_minutes=60
    )

    result = _run(component)

    assert result["duration_minutes"] == 60
    assert result["free_ranges"] == ["09:00-10:00", "10:30-12:00"]
    # 09:30 would overlap the busy slot; 11:00 is the last start that ends by 12:00.
    assert result["available_starts"] == ["09:00", "10:30", "11:00"]


def test_off_grid_busy_end_rounds_next_start_up_to_the_grid():
    component, _ = _make_component(service=_FakeCalendarService(busy=[_busy("09:00", "09:40")]))

    result = _run(component)

    assert result["free_ranges"] == ["09:40-12:00"]
    assert result["available_starts"] == ["10:00", "10:30", "11:00", "11:30"]


def test_overlapping_and_unsorted_busy_slots_are_merged():
    busy = [_busy("10:30", "11:00"), _busy("09:00", "10:00"), _busy("09:30", "10:45")]
    component, _ = _make_component(service=_FakeCalendarService(busy=busy))

    result = _run(component)

    assert result["free_ranges"] == ["11:00-12:00"]
    assert result["available_starts"] == ["11:00", "11:30"]


def test_fully_booked_day_says_so():
    component, _ = _make_component(service=_FakeCalendarService(busy=[_busy("08:00", "13:00")]))

    result = _run(component)

    assert result["success"] is True
    assert result["available_starts"] == []
    assert "No hay huecos" in result["message"]


def test_non_business_day_returns_no_slots_without_calling_google():
    component, fake = _make_component(date="2030-01-12")  # Saturday

    result = _run(component)

    assert result["success"] is True
    assert result["available_starts"] == []
    assert "No se dan citas" in result["message"]
    assert fake.queries == []


def test_empty_business_hours_means_whole_day():
    component, _ = _make_component(business_hours="", slot_step_minutes=360, duration_minutes=60)

    result = _run(component)

    assert result["free_ranges"] == ["00:00-24:00"]
    assert result["available_starts"] == ["00:00", "06:00", "12:00", "18:00"]


def test_freebusy_queries_the_whole_local_day():
    component, fake = _make_component()

    _run(component)

    body = fake.queries[0]
    assert body["timeMin"] == f"{_MONDAY}T00:00:00+01:00"
    assert body["timeMax"] == "2030-01-08T00:00:00+01:00"
    assert body["items"] == [{"id": _CALENDAR}]


def test_today_only_offers_starts_after_now():
    class _FixedNow(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return real_datetime.fromisoformat(f"{_MONDAY}T10:10:00+01:00").astimezone(tz)

    component, _ = _make_component()
    original = google_calendar_availability.datetime
    google_calendar_availability.datetime = _FixedNow
    try:
        result = _run(component)
    finally:
        google_calendar_availability.datetime = original

    assert result["available_starts"] == ["10:30", "11:00", "11:30"]


def test_today_after_closing_says_no_slots_left():
    class _FixedNow(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return real_datetime.fromisoformat(f"{_MONDAY}T11:50:00+01:00").astimezone(tz)

    component, fake = _make_component()
    original = google_calendar_availability.datetime
    google_calendar_availability.datetime = _FixedNow
    try:
        result = _run(component)
    finally:
        google_calendar_availability.datetime = original

    assert result["available_starts"] == []
    assert "No quedan huecos" in result["message"]
    assert fake.queries == []


def test_past_date_is_rejected():
    component, _ = _make_component(date="2020-01-06")

    result = _run(component)

    assert result["success"] is False
    assert "ya pasó" in result["error"]


def test_invalid_date_is_reported():
    component, _ = _make_component(date="el lunes")

    result = _run(component)

    assert result["success"] is False
    assert "YYYY-MM-DD" in result["error"]


def test_datetime_value_uses_its_day():
    component, fake = _make_component(date=f"{_MONDAY}T15:00")

    result = _run(component)

    assert result["date"] == _MONDAY
    assert len(fake.queries) == 1


def test_invalid_business_hours_are_reported():
    for value in ("de 9 a 6", "18:00-09:00", "25:00-26:00"):
        component, _ = _make_component(business_hours=value)

        result = _run(component)

        assert result["success"] is False, value
        assert "Horario de citas" in result["error"]


def test_invalid_business_days_are_reported():
    component, _ = _make_component(business_days="lunes")

    result = _run(component)

    assert result["success"] is False
    assert "Días de citas" in result["error"]


def test_invalid_timezone_is_reported():
    component, _ = _make_component(timezone="Madrid")

    result = _run(component)

    assert result["success"] is False
    assert "Zona horaria" in result["error"]


def test_zero_step_is_reported():
    component, _ = _make_component(slot_step_minutes=0)

    result = _run(component)

    assert result["success"] is False
    assert "Intervalo" in result["error"]


def test_calendar_error_is_reported():
    component, _ = _make_component(service=_FakeCalendarService(errors=[{"reason": "notFound"}]))

    result = _run(component)

    assert result["success"] is False
    assert "notFound" in result["error"]


def test_calendar_not_shared_explains_how_to_fix():
    component, _ = _make_component(service=_FakeCalendarService(raise_on_call=_FakeHttpError(403)))

    result = _run(component)

    assert result["success"] is False
    assert "compartido" in result["error"]


def test_rejected_credential_is_reported_not_raised():
    error = _FakeGoogleAuthError("invalid_grant: account not found")
    component, _ = _make_component(service=_FakeCalendarService(raise_on_call=error))

    result = _run(component)

    assert result["success"] is False
    assert "invalid_grant" in result["error"]


def test_network_failure_is_reported_not_raised():
    component, _ = _make_component(service=_FakeCalendarService(raise_on_call=ConnectionError("timed out")))

    result = _run(component)

    assert result["success"] is False
    assert "No se pudo conectar" in result["error"]


def test_build_service_uses_read_only_scope():
    component = GoogleCalendarAvailabilityComponent()
    component.service_account_json = json.dumps({"client_email": "bot@proj.iam.gserviceaccount.com"})

    _, args, kwargs = component._build_service()

    assert args == ("calendar", "v3")
    assert kwargs["credentials"][2] == ("https://www.googleapis.com/auth/calendar.readonly",)


def test_invalid_service_account_json_is_reported():
    component = GoogleCalendarAvailabilityComponent()
    component.service_account_json = "no es json"

    try:
        component._build_service()
    except google_calendar_availability.AvailabilityError as exc:
        assert "JSON" in str(exc)
    else:
        raise AssertionError("expected AvailabilityError")
