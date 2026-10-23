# Ledger & Payments API

A double-entry ledger and wallet-transfer REST API built with FastAPI, PostgreSQL, and plain psycopg.

## Quickstart

```bash
# Start Postgres via Docker Compose
docker compose up -d

# Create virtual environment and install deps
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"

# Copy env and run migrations
cp .env.example .env
alembic upgrade head

# Run the server
uvicorn app.main:app --reload
```

Then visit `http://localhost:8000/docs`.

## Alembic note

Alembic depends on SQLAlchemy internally, so `pip` will install it. **Use Alembic only to run migrations** (with the URL `postgresql+psycopg://...`). Application code uses psycopg directly and has no SQLAlchemy dependency.

## Architecture

See [docs/architecture.md](docs/architecture.md) and [docs/adr/](docs/adr/) for design decisions.

## Running tests

```bash
pytest
```

Tests spin up a real Postgres container via Testcontainers and run migrations against it.

## Invariants defended in interviews

1. Every transaction's debits equal its credits.
2. Ledger entries are never updated or deleted.
3. A wallet balance never goes below zero.
4. A retried request never moves money twice.
