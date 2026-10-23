"""Ledger repository: raw SQL for transactions, ledger_entries, and idempotency keys."""

from uuid import UUID

import psycopg
from psycopg.rows import class_row


async def insert_transaction(
    conn: psycopg.AsyncConnection,
    tx_type: str,
    reference: str,
    created_by: UUID,
) -> UUID:
    async with conn.cursor(row_factory=class_row(UUID)) as cur:
        await cur.execute(
            """
            INSERT INTO transactions (id, type, reference, created_by, created_at)
            VALUES (gen_random_uuid(), %s, %s, %s, now())
            RETURNING id
            """,
            (tx_type, reference, created_by),
        )
        row = await cur.fetchone()
        if row is None:
            raise RuntimeError("Failed to insert transaction")
        return row[0]


async def insert_ledger_entry(
    conn: psycopg.AsyncConnection,
    transaction_id: UUID,
    account_id: UUID,
    direction: str,
    amount_minor: int,
    balance_after_minor: int,
) -> int:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO ledger_entries
                (transaction_id, account_id, direction,
                 amount_minor, balance_after_minor, created_at)
            VALUES (%s, %s, %s, %s, %s, now())
            """,
            (transaction_id, account_id, direction, amount_minor, balance_after_minor),
        )
        return cur.rowcount


async def update_account_balance(conn: psycopg.AsyncConnection, account_id: UUID, new_balance: int) -> None:
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE accounts SET balance_minor = %s WHERE id = %s",
            (new_balance, account_id),
        )


async def upsert_idempotency_key(
    conn: psycopg.AsyncConnection,
    user_id: UUID,
    key: str,
    request_hash: str,
    transaction_id: UUID,
    response_code: int,
    response_body: dict,
) -> bool:
    """Returns True if this was a new insert, False if conflict."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO idempotency_keys
                (user_id, key, request_hash, transaction_id,
                 response_code, response_body, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (user_id, key) DO NOTHING
            """,
            (user_id, key, request_hash, transaction_id, response_code, response_body),
        )
        return cur.rowcount > 0


async def get_idempotency_key(
    conn: psycopg.AsyncConnection,
    user_id: UUID,
    key: str,
) -> dict | None:
    async with conn.cursor(row_factory=psycopg.extras.RealDictRow) as cur:
        await cur.execute(
            "SELECT * FROM idempotency_keys WHERE user_id = %s AND key = %s",
            (user_id, key),
        )
        return await cur.fetchone()


async def update_idempotency_key_response(
    conn: psycopg.AsyncConnection,
    user_id: UUID,
    key: str,
    request_hash: str,
    transaction_id: UUID,
    response_code: int,
    response_body: dict,
) -> None:
    """Update an existing idempotency key with new response data."""
    async with conn.cursor() as cur:
        await cur.execute(
            """
            UPDATE idempotency_keys
            SET request_hash = %s, transaction_id = %s, response_code = %s, response_body = %s
            WHERE user_id = %s AND key = %s
            """,
            (request_hash, transaction_id, response_code, response_body, user_id, key),
        )


async def get_ledger_entries(
    conn: psycopg.AsyncConnection,
    account_id: UUID,
    cursor: int | None = None,
    limit: int = 20,
) -> list[dict]:
    async with conn.cursor(row_factory=psycopg.extras.RealDictRow) as cur:
        if cursor is not None:
            await cur.execute(
                """
                SELECT * FROM ledger_entries
                WHERE account_id = %s AND id < %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (account_id, cursor, limit),
            )
        else:
            await cur.execute(
                """
                SELECT * FROM ledger_entries
                WHERE account_id = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (account_id, limit),
            )
        return await cur.fetchall()
