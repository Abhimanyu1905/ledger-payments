"""Pydantic schemas for request/response validation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# --- Auth ---

class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Accounts ---

class CreateWalletRequest(BaseModel):
    pass  # wallet always created for the authenticated user


class AccountResponse(BaseModel):
    id: UUID
    user_id: UUID
    kind: str
    currency: str
    balance_minor: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Ledger entries ---

class LedgerEntryResponse(BaseModel):
    id: int
    transaction_id: UUID
    account_id: UUID
    direction: str
    amount_minor: int
    balance_after_minor: int
    created_at: datetime

    model_config = {"from_attributes": True}


class EntriesQuery(BaseModel):
    cursor: int | None = None
    limit: int = Field(default=20, le=100)


# --- Deposits ---

class DepositRequest(BaseModel):
    amount_minor: int = Field(gt=0)


# --- Transfers ---

class TransferRequest(BaseModel):
    source_account_id: UUID
    destination_account_id: UUID
    amount_minor: int = Field(gt=0)


class TransferResponse(BaseModel):
    id: UUID
    type: str
    reference: str
    created_by: UUID
    created_at: datetime

    model_config = {"from_attributes": True}
