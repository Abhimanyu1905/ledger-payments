"""Transfer service: move money between wallets with idempotency."""

from uuid import UUID

import psycopg
import psycopg.types.json

from app.errors import IdempotencyConflictError, InsufficientFundsError, NotFoundError
from app.repositories import accounts, ledger


async def transfer(
    conn: psycopg.AsyncConnection,
    source_account_id: UUID,
    destination_account_id: UUID,
    amount_minor: int,
    idempotency_key: str,
    user_id: UUID,
) -> dict:
    if source_account_id == destination_account_id:
        raise ValueError("Cannot transfer to same account")

    # Check idempotency key first
    existing = await ledger.get_idempotency_key(conn, user_id, idempotency_key)
    if existing:
        if existing["request_hash"] != f"TRANSFER:{source_account_id}:{destination_account_id}:{amount_minor}":
            raise IdempotencyConflictError("Idempotency key conflict")
        return {
            "transaction_id": str(existing["transaction_id"]),
            "source_account_id": str(source_account_id),
            "destination_account_id": str(destination_account_id),
            "amount_minor": amount_minor,
        }

    # Lock both accounts in sorted order to prevent deadlocks
    locked = await accounts.lock_accounts_for_update(conn, [source_account_id, destination_account_id])
    if len(locked) != 2:
        raise NotFoundError("One or both accounts not found")

    source = next(a for a in locked if a["id"] == source_account_id)
    dest = next(a for a in locked if a["id"] == destination_account_id)

    # Validate ownership
    if str(source["user_id"]) != str(user_id):
        raise ValueError("Forbidden")

    # Validate status
    if source["status"] != "ACTIVE" or dest["status"] != "ACTIVE":
        raise ValueError("One or both accounts are not active")

    # Check sufficient funds
    if source["balance_minor"] < amount_minor:
        raise InsufficientFundsError("Insufficient funds")

    # Create transaction
    tx_id = await ledger.insert_transaction(
        conn, "TRANSFER", f"TRF-{idempotency_key}", user_id
    )

    # Debit source, credit destination
    new_source_balance = source["balance_minor"] - amount_minor
    new_dest_balance = dest["balance_minor"] + amount_minor

    await ledger.update_account_balance(conn, source_account_id, new_source_balance)
    await ledger.update_account_balance(conn, destination_account_id, new_dest_balance)
    await ledger.insert_ledger_entry(
        conn, tx_id, source_account_id, "DEBIT", amount_minor, new_source_balance
    )
    await ledger.insert_ledger_entry(
        conn, tx_id, destination_account_id, "CREDIT", amount_minor, new_dest_balance
    )

    # Save idempotency key
    response_body = {
        "transaction_id": str(tx_id),
        "source_account_id": str(source_account_id),
        "destination_account_id": str(destination_account_id),
        "amount_minor": amount_minor,
    }
    await ledger.upsert_idempotency_key(
        conn, user_id, idempotency_key, f"TRANSFER:{source_account_id}:{destination_account_id}:{amount_minor}",
        tx_id, 201, response_body
    )

    return response_body
