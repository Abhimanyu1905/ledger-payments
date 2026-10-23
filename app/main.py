"""FastAPI routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from app.db import get_conn
from app.repositories import accounts
from app.schemas.models import (
    AccountResponse,
    DepositRequest,
    EntriesQuery,
    LedgerEntryResponse,
    LoginRequest,
    RegisterRequest,
    TransferRequest,
)
from app.security import create_access_token, decode_access_token
from app.services import deposits, transfers

router = APIRouter()


async def get_current_user(request: Request) -> dict:
    """Extract and validate JWT from Authorization header."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authorization header")
    token = auth_header[len("Bearer "):]
    try:
        user_id = decode_access_token(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    return {"user_id": UUID(user_id)}


@router.post("/auth/register")
async def register(req: RegisterRequest, conn=Depends(get_conn)):
    result = await deposits.register_user(conn, req.email, req.password)
    token = create_access_token(str(result["user_id"]))
    return {"access_token": token, "token_type": "bearer", "account_id": result["account_id"]}


@router.post("/auth/login")
async def login(req: LoginRequest, conn=Depends(get_conn)):
    result = await deposits.login_user(conn, req.email, req.password)
    token = create_access_token(str(result["user_id"]))
    return {"access_token": token, "token_type": "bearer"}


@router.get("/accounts")
async def list_accounts(user=Depends(get_current_user), conn=Depends(get_conn)):
    accs = await accounts.get_accounts_by_user(conn, user["user_id"])
    return [AccountResponse.model_validate(a) for a in accs]


@router.get("/accounts/{account_id}")
async def get_account(account_id: UUID, user=Depends(get_current_user), conn=Depends(get_conn)):
    acc = await accounts.get_account(conn, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    if str(acc["user_id"]) != str(user["user_id"]):
        raise HTTPException(status_code=403, detail="Forbidden")
    return AccountResponse.model_validate(acc)


@router.get("/accounts/{account_id}/entries")
async def get_entries(
    account_id: UUID,
    query: EntriesQuery = ...,
    user=Depends(get_current_user),
    conn=Depends(get_conn),
):
    acc = await accounts.get_account(conn, account_id)
    if not acc:
        raise HTTPException(status_code=404, detail="Account not found")
    if str(acc["user_id"]) != str(user["user_id"]):
        raise HTTPException(status_code=403, detail="Forbidden")
    entries = await accounts.get_ledger_entries(conn, account_id, query.cursor, query.limit)
    return [LedgerEntryResponse.model_validate(e) for e in entries]


@router.post("/accounts/{account_id}/deposits")
async def deposit(
    account_id: UUID,
    req: DepositRequest,
    idempotency_key: str = Header(...),
    user=Depends(get_current_user),
    conn=Depends(get_conn),
):
    result = await deposits.deposit(conn, account_id, req.amount_minor, idempotency_key, user["user_id"])
    return JSONResponse(status_code=201, content=result)


@router.post("/transfers")
async def transfer(
    req: TransferRequest,
    idempotency_key: str = Header(...),
    user=Depends(get_current_user),
    conn=Depends(get_conn),
):
    result = await transfers.transfer(
        conn, req.source_account_id, req.destination_account_id,
        req.amount_minor, idempotency_key, user["user_id"],
    )
    return JSONResponse(status_code=201, content=result)


@router.get("/transfers/{transaction_id}")
async def get_transfer(transaction_id: UUID, user=Depends(get_current_user), conn=Depends(get_conn)):
    # Simplified - in real app would query transactions table
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/health/db")
async def health_db(conn=Depends(get_conn)):
    async with conn.cursor() as cur:
        await cur.execute("SELECT 1")
        return {"status": "ok", "db": "connected"}
