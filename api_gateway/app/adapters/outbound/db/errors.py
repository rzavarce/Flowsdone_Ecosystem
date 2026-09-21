"""Translation of database errors into domain errors."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy.exc import IntegrityError

from app.domain.ports.outbound import AlreadyExistsError

_UNIQUE_VIOLATION = "duplicate key value violates unique constraint"


@contextmanager
def duplicate_as_already_exists() -> Iterator[None]:
    """Turn a unique-constraint violation into `AlreadyExistsError`.

    Wrap the `commit()` of a `create`/`update`. Other integrity errors (a
    missing foreign key, a failed CHECK) are NOT duplicates and propagate
    unchanged, so real bugs are not disguised as conflicts.

    Raises:
        AlreadyExistsError: If the database reports a unique violation.
    """
    try:
        yield
    except IntegrityError as exc:
        if _UNIQUE_VIOLATION in str(exc.orig):
            raise AlreadyExistsError(str(exc.orig)) from exc
        raise
