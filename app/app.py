"""FastAPI application factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from psycopg_pool import AsyncConnectionPool

from app.config import settings
from app.main import router as api_router

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
    app = FastAPI(
        title="Ledger API",
        description="Double-entry ledger and wallet-transfer REST API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/")
    async def root():
        return {"message": "Ledger API", "docs": "/docs"}

    return app


app = create_app()
