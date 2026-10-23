"""PostgreSQL connection pool and FastAPI lifespan."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI
from psycopg_pool import AsyncConnectionPool

from app.config import settings

_pool: AsyncConnectionPool | None = None


async def get_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        _pool = AsyncConnectionPool(
            conninfo=settings.database_url,
            min_size=2,
            max_size=10,
            timeout=30,
        )
    return _pool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    pool = await get_pool()
    await pool.open(wait=True)
    yield
    await pool.close()
    global _pool
    _pool = None


def create_app() -> FastAPI:
    from app.main import _register_routes

    app = FastAPI(title="Ledger API", lifespan=lifespan)
    _register_routes(app)
    return app


async def get_conn() -> AsyncGenerator[psycopg.AsyncConnection, None]:
    """Yield a connection from the pool inside an autocommit-free transaction."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.transaction():
        yield conn
