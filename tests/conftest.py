"""Test configuration with Testcontainers for PostgreSQL."""

import os
import subprocess
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from psycopg_pool import AsyncConnectionPool
from testcontainers.community.postgres import PostgresContainer

from app.app import create_app

_ALEMBIC_INI_BACKUP = None


@pytest.fixture(scope="session", autouse=True)
def patch_alembic_ini_for_test_db(database_url):
    """Override alembic.ini sqlalchemy.url to point at the test container."""
    global _ALEMBIC_INI_BACKUP
    ini_path = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
    with open(ini_path) as f:
        _ALEMBIC_INI_BACKUP = f.read()
    patched = _ALEMBIC_INI_BACKUP.replace(
        "sqlalchemy.url = postgresql://ledger:ledger@localhost:5433/ledger",
        f"sqlalchemy.url = {database_url}",
    )
    with open(ini_path, "w") as f:
        f.write(patched)
    yield
    # Restore original
    with open(ini_path, "w") as f:
        f.write(_ALEMBIC_INI_BACKUP)
    _ALEMBIC_INI_BACKUP = None


@pytest.fixture(scope="session", autouse=True)
def run_migrations_on_test_db(postgres_container, database_url):
    """Run alembic migrations against the test database before any tests."""
    result = subprocess.run(
        ["python", "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        cwd=os.path.join(os.path.dirname(__file__), ".."),
        env={**os.environ, "DATABASE_URL": database_url},
    )
    if result.returncode != 0:
        raise RuntimeError(f"Alembic migration failed:\n{result.stderr}")
    yield


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
    """Generate database URL from container."""
    url = postgres_container.get_connection_url()
    # Convert postgresql+psycopg2:// to postgresql:// for psycopg3
    return url.replace("postgresql+psycopg2://", "postgresql://")


@pytest.fixture(scope="session")
def app(database_url):
    """Create FastAPI app with test database URL."""
    import os

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
