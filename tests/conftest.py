"""Test configuration with Testcontainers for PostgreSQL."""

import os
import subprocess
import sys
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from psycopg_pool import AsyncConnectionPool
from testcontainers.community.postgres import PostgresContainer

from app.app import create_app

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_ALEMBIC_INI = os.path.join(_ROOT, "alembic.ini")
_ALEMBIC_INI_BACKUP: str | None = None


@pytest.fixture(scope="session")
def postgres_container():
    """Session-scoped PostgreSQL container."""
    with PostgresContainer(
        "postgres:16",
        username="ledger",
        password="ledger",
        dbname="ledger",
    ) as container:
        yield container


@pytest.fixture(scope="session")
def database_url(postgres_container):
    """Generate database URL from container (psycopg3-compatible)."""
    url = postgres_container.get_connection_url()
    return url.replace("postgresql+psycopg2://", "postgresql://")


@pytest.fixture(scope="session", autouse=True)
def run_migrations_on_test_db(database_url):
    """Patch alembic.ini URL, run migrations, then restore."""
    global _ALEMBIC_INI_BACKUP
    with open(_ALEMBIC_INI) as f:
        _ALEMBIC_INI_BACKUP = f.read()
    patched = _ALEMBIC_INI_BACKUP.replace(
        "sqlalchemy.url = postgresql://ledger:ledger@localhost:5433/ledger",
        f"sqlalchemy.url = {database_url}",
    )
    with open(_ALEMBIC_INI, "w") as f:
        f.write(patched)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd=_ROOT,
            env={**os.environ, "DATABASE_URL": database_url},
        )
        if result.returncode != 0:
            raise RuntimeError(f"Alembic migration failed:\n{result.stderr}")
        yield
    finally:
        with open(_ALEMBIC_INI, "w") as f:
            f.write(_ALEMBIC_INI_BACKUP)
        _ALEMBIC_INI_BACKUP = None


@pytest.fixture(scope="session")
def app(database_url):
    """Create FastAPI app with test database URL."""
    os.environ["DATABASE_URL"] = database_url

    from app.config import settings

    settings.database_url = database_url

    return create_app()


@pytest_asyncio.fixture
async def client(app, database_url):
    """Async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


@pytest_asyncio.fixture
async def pool(database_url: str) -> AsyncGenerator[AsyncConnectionPool, None]:
    """Connection pool for direct DB operations."""
    p = AsyncConnectionPool(
        conninfo=database_url,
        min_size=1,
        max_size=2,
        open=False,
    )
    await p.open()
    try:
        yield p
    finally:
        await p.close()


@pytest.fixture
async def truncate_tables(pool):
    """Truncate all tables between tests."""
    yield
    async with pool.connection() as conn, conn.transaction():
        await conn.execute(
            "TRUNCATE TABLE outbox_events, idempotency_keys, ledger_entries, "
            "transactions, accounts, users CASCADE"
        )
