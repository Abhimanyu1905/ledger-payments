"""Auth repository: raw SQL for users table."""

from uuid import UUID

import psycopg
from psycopg.rows import class_row


async def create_user(conn: psycopg.AsyncConnection, email: str, password_hash: str) -> UUID:
    async with conn.cursor(row_factory=class_row(UUID)) as cur:
        await cur.execute(
            """
            INSERT INTO users (id, email, password_hash, created_at)
            VALUES (gen_random_uuid(), %s, %s, now())
            RETURNING id
            """,
            (email, password_hash),
        )
        row = await cur.fetchone()
        if row is None:
            raise RuntimeError("Failed to create user")
        return row[0]


async def find_user_by_email(conn: psycopg.AsyncConnection, email: str) -> dict | None:
    async with conn.cursor(row_factory=psycopg.extras.RealDictRow) as cur:
        await cur.execute(
            "SELECT id, email, password_hash FROM users WHERE lower(email) = lower(%s)",
            (email,),
        )
        return await cur.fetchone()


async def find_user(conn: psycopg.AsyncConnection, user_id: UUID) -> dict | None:
    async with conn.cursor(row_factory=psycopg.extras.RealDictRow) as cur:
        await cur.execute("SELECT id, email FROM users WHERE id = %s", (user_id,))
        return await cur.fetchone()
