"""Migration tests - verify schema exists."""

import pytest
from psycopg_pool import AsyncConnectionPool


@pytest.mark.asyncio
async def test_users_table_exists(pool: AsyncConnectionPool):
    """Users table should exist after migrations."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'users'
                )
            """)
        result = await cur.fetchone()
        assert result[0] is True


@pytest.mark.asyncio
async def test_unique_email_index(pool: AsyncConnectionPool):
    """Unique index on lower(email) should exist."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("""
                SELECT EXISTS (
                    SELECT FROM pg_indexes
                    WHERE tablename = 'users'
                    AND indexname = 'idx_users_lower_email'
                )
            """)
        result = await cur.fetchone()
        assert result[0] is True


@pytest.mark.asyncio
async def test_accounts_table_exists(pool: AsyncConnectionPool):
    """Accounts table should exist."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'accounts'
                )
            """)
        result = await cur.fetchone()
        assert result[0] is True


@pytest.mark.asyncio
async def test_transactions_table_exists(pool: AsyncConnectionPool):
    """Transactions table should exist."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'transactions'
                )
            """)
        result = await cur.fetchone()
        assert result[0] is True


@pytest.mark.asyncio
async def test_ledger_entries_table_exists(pool: AsyncConnectionPool):
    """Ledger entries table should exist."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'ledger_entries'
                )
            """)
        result = await cur.fetchone()
        assert result[0] is True


@pytest.mark.asyncio
async def test_idempotency_keys_table_exists(pool: AsyncConnectionPool):
    """Idempotency keys table should exist."""
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'idempotency_keys'
                )
            """)
        result = await cur.fetchone()
        assert result[0] is True
