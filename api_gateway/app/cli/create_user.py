"""Create a console user from the command line.

There is no public sign-up, and the first admin has to come from
somewhere, so users are created by an operator with shell access:

    docker compose exec api python -m app.cli.create_user \\
        --email ana@empresa.com --name "Ana Pérez" --role admin

    docker compose exec api python -m app.cli.create_user \\
        --email carla@cliente.com --name "Carla" --role client --tenant clinica-vital

The password is asked interactively (hidden), or read from stdin with
`--password-stdin`. It is never taken from a flag (it would end up in the
shell history and the process list).
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from typing import List, Optional, Sequence
from uuid import UUID

from app.adapters.outbound.db.tenant_repository import SqlAlchemyTenantRepository
from app.adapters.outbound.db.user_repository import SqlAlchemyUserRepository
from app.adapters.outbound.security.scrypt_password_hasher import ScryptPasswordHasher
from app.application.use_cases.create_user import MIN_PASSWORD_LENGTH, CreateUserUseCase
from app.domain.models.user import USER_ROLES
from app.domain.ports.outbound import UserAlreadyExistsError
from app.infrastructure.database import create_engine, create_sessionmaker


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse the command line.

    Args:
        argv (Optional[Sequence[str]]): Arguments (defaults to `sys.argv`).

    Returns:
        argparse.Namespace: The parsed options.
    """
    parser = argparse.ArgumentParser(prog="python -m app.cli.create_user", description=__doc__.split("\n\n")[0])
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", required=True, choices=USER_ROLES)
    parser.add_argument(
        "--tenant",
        action="append",
        default=[],
        metavar="SLUG",
        help="tenant slug to assign (repeatable). Required for every role except admin.",
    )
    parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="read the password from stdin instead of prompting",
    )
    return parser.parse_args(argv)


def read_password(from_stdin: bool) -> str:
    """Obtain the password without exposing it on the command line.

    Args:
        from_stdin (bool): Read one line from stdin instead of prompting.

    Returns:
        str: The password.

    Raises:
        SystemExit: If the two interactive entries differ.
    """
    if from_stdin:
        return sys.stdin.readline().rstrip("\r\n")
    first = getpass.getpass(f"Password (min {MIN_PASSWORD_LENGTH} chars): ")
    if first != getpass.getpass("Repeat password: "):
        raise SystemExit("error: passwords do not match")
    return first


async def run(args: argparse.Namespace, password: str) -> int:
    """Create the user.

    Args:
        args (argparse.Namespace): Parsed options.
        password (str): Plaintext password.

    Returns:
        int: Process exit code (0 on success).
    """
    engine = create_engine()
    try:
        sessionmaker = create_sessionmaker(engine)
        tenant_repo = SqlAlchemyTenantRepository(sessionmaker)
        use_case = CreateUserUseCase(
            user_repo=SqlAlchemyUserRepository(sessionmaker),
            tenant_repo=tenant_repo,
            hasher=ScryptPasswordHasher(),
        )

        tenant_ids: List[UUID] = []
        if args.tenant:
            by_slug = {t.slug: t.id for t in await tenant_repo.list()}
            unknown = [s for s in args.tenant if s not in by_slug]
            if unknown:
                print(f"error: unknown tenant slug(s): {', '.join(unknown)}", file=sys.stderr)
                print(f"known: {', '.join(sorted(by_slug)) or '(none)'}", file=sys.stderr)
                return 1
            tenant_ids = [by_slug[s] for s in args.tenant]

        try:
            user = await use_case.execute(
                email=args.email,
                name=args.name,
                role=args.role,
                password=password,
                tenant_ids=tenant_ids,
            )
        except UserAlreadyExistsError:
            print(f"error: a user with email {args.email.strip().lower()} already exists", file=sys.stderr)
            return 1
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"created {user.role} {user.email} ({user.id})")
        return 0
    finally:
        await engine.dispose()


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Entry point.

    Args:
        argv (Optional[Sequence[str]]): Arguments (defaults to `sys.argv`).
    """
    args = parse_args(argv)
    raise SystemExit(asyncio.run(run(args, read_password(args.password_stdin))))


if __name__ == "__main__":
    main()
