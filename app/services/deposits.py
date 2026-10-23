"""Deposit service: credit a wallet from the SYSTEM account."""

from uuid import UUID

import psycopg
import psycopg.types.json

from app.errors import NotFoundError
from app.repositories import accounts, ledger, users
from app.security import hash_password, verify_password


async def register_user(conn: psycopg.AsyncConnection, email: str, password: str) -> dict:
    existing = await users.find_user_by_email(conn, email)
    if existing:
        raise ValueError("Email already registered")

    user_id = await users.create_user(conn, email, hash_password(password))
    account_id = await accounts.create_account(conn, user_id, "WALLET")

    return {"user_id": str(user_id), "account_id": str(account_id)}


async def login_user(conn: psycopg.AsyncConnection, email: str, password: str) -> dict:
    user = await users.find_user_by_email(conn, email)
    if not user:
        raise ValueError("Invalid credentials")
    if not verify_password(password, user["password_hash"]):
        raise ValueError("Invalid credentials")
    return {"user_id": str(user["id"])}


async def deposit(
    conn: psycopg.AsyncConnection,
    account_id: UUID,
    amount_minor: int,
    idempotency_key: str,
    user_id: UUID,
) -> dict:
    account = await accounts.get_account(conn, account_id)
    if not account:
        raise NotFoundError("Account not found")
    if str(account["user_id"]) != str(user_id):
        raise ValueError("Forbidden")
    if account["status"] != "ACTIVE":
        raise ValueError("Account is not active")

    # Insert idempotency key first
    await ledger.upsert_idempotency_key(
        conn, user_id, idempotency_key, f"DEPOSIT:{amount_minor}", None, 0, {}
    )

    # System account ID - fixed for simplicity
    system_account_id = UUID("00000000-0000-0000-0000-000000000001")

    # Lock both accounts in sorted order
    locked = await accounts.lock_accounts_for_update(conn, [account_id, system_account_id])
    if len(locked) != 2:
        raise NotFoundError("Account not found")

    account_data = next(a for a in locked if a["id"] == account_id)
    system_data = next(a for a in locked if a["id"] == system_account_id)

    # Create transaction
    tx_id = await ledger.insert_transaction(conn, "DEPOSIT", f"DEP-{idempotency_key}", user_id)

    # Debit system, credit wallet
    new_system_balance = system_data["balance_minor"] - amount_minor
    new_wallet_balance = account_data["balance_minor"] + amount_minor

    await ledger.update_account_balance(conn, system_account_id, new_system_balance)
    await ledger.update_account_balance(conn, account_id, new_wallet_balance)
    await ledger.insert_ledger_entry(conn, tx_id, system_account_id, "DEBIT", amount_minor, new_system_balance)
    await ledger.insert_ledger_entry(conn, tx_id, account_id, "CREDIT", amount_minor, new_wallet_balance)

    # Update idempotency key with result
    response_body = {"transaction_id": str(tx_id), "account_id": str(account_id), "amount_minor": amount_minor}
    await ledger.update_idempotency_key_response(
        conn, user_id, idempotency_key, f"DEPOSIT:{amount_minor}", tx_id, 201, response_body
    )

    return response_body
