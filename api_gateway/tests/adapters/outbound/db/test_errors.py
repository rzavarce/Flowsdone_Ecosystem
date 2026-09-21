"""Tests for the database-error translation helper."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.adapters.outbound.db.errors import duplicate_as_already_exists
from app.domain.ports.outbound import AlreadyExistsError

UNIQUE = 'duplicate key value violates unique constraint "uq_channel_connections_type_external"'
FOREIGN_KEY = 'insert or update on table "channel_connections" violates foreign key constraint "fk_agent"'


def _integrity(message: str) -> IntegrityError:
    return IntegrityError("INSERT ...", {}, Exception(message))


def test_a_unique_violation_becomes_already_exists_and_keeps_the_cause():
    with pytest.raises(AlreadyExistsError) as info:
        with duplicate_as_already_exists():
            raise _integrity(UNIQUE)
    assert "uq_channel_connections_type_external" in str(info.value)
    assert isinstance(info.value.__cause__, IntegrityError)


def test_other_integrity_errors_are_not_disguised_as_conflicts():
    # Una FK rota o un CHECK fallido son bugs reales (500), no "ya existe" (409).
    with pytest.raises(IntegrityError):
        with duplicate_as_already_exists():
            raise _integrity(FOREIGN_KEY)


def test_other_exceptions_and_the_happy_path_are_untouched():
    with duplicate_as_already_exists():
        pass
    with pytest.raises(ValueError):
        with duplicate_as_already_exists():
            raise ValueError("otra cosa")
