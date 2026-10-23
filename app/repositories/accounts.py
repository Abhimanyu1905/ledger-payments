"""Account repository: raw SQL for accounts table."""

from uuid import UUID

import psycopg
from psycopg.rows import class_row


async def create_account(
    conn: psycopg.AsyncConnection,
    user_id: UUID,
    kind: str,
    currency: str = "INR",
) -> UUID:
    async with conn.cursor(row_factory=class_row(UUID)) as cur:
        await cur.execute(
            """
            INSERT INTO accounts (id, user_id, kind, currency, balance_minor, status, created_at)
            VALUES (gen_random_uuid(), %s, %s, %s, 0, 'ACTIVE', now())
            RETURNING id
            """,
            (user_id, kind, currency),
        )
        row = await cur.fetchone()
        if row is None:
            raise RuntimeError("Failed to create account")
        return row[0]


async def get_account(conn: psycopg.AsyncConnection, account_id: UUID) -> dict | None:
    async with conn.cursor(row_factory=psycopg.extras.RealDictRow) as cur:
        await cur.execute("SELECT * FROM accounts WHERE id = %s", (account_id,))
        return await cur.fetchone()


async def get_accounts_by_user(conn: psycopg.AsyncConnection, user_id: UUID) -> list[dict]:
    async with conn.cursor(row_factory=psycopg.extras.RealDictRow) as cur:
        await cur.execute(
            "SELECT * FROM accounts WHERE user_id = %s ORDER BY created_at",
            (user_id,),
        )
        return await cur.fetchall()


async def lock_accounts_for_update(conn: psycopg.AsyncConnection, account_ids: list[UUID]) -> list[dict]:
    """Lock accounts in sorted ID order to prevent deadlocks."""
    sorted_ids = sorted(account_ids, key=lambda x: str(x))
    async with conn.cursor(row_factory=psycopg.extras.RealDictRow) as cur:
        await cur.execute(
            "SELECT * FROM accounts WHERE id = ANY(%s) ORDER BY id FOR UPDATE",
            (sorted_ids,),
        )
        return await cur.fetchall()
