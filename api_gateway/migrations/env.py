from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Asegura que la raíz del repo y api_gateway/ estén en sys.path sin
# importar desde dónde se invoque `alembic` (docker-compose lo corre
# con cwd=/app, WORKDIR del Dockerfile). api_gateway/ hace falta
# además de la raíz porque `app` (el código de la aplicación, físicamente
# en api_gateway/app/) se importa sin el prefijo api_gateway. - igual
# que en app/ mismo y en los tests, ver pyproject.toml [tool.pytest.ini_options].
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
API_GATEWAY_DIR = os.path.join(REPO_ROOT, "api_gateway")
for _path in (REPO_ROOT, API_GATEWAY_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from app.adapters.outbound.db.models import Base  # noqa: E402
from app.core.config import settings  # noqa: E402

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL_SQLALCHEMY or "")

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
