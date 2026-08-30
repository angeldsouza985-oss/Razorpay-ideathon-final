# BillGuard AI

BillGuard finds revenue a billing system forgot by comparing contract, usage, invoice, and payment evidence. This Phase 1 prototype is a deliberately deterministic FastAPI service: it emits `POTENTIAL LEAKAGE`, never claims validation or recovery, and leaves AI investigation for a later phase.

## Architecture
Python + FastAPI + SQLAlchemy + SQLite. `revenue_engine.py` uses `Decimal` for contract pricing, discounts, escalations, usage overage, amendments, service charges, tax, and comparisons. Synthetic data uses seed 42 and includes Indian B2B companies, the Acme February case, all requested discrepancy scenarios, and an approved amendment.

## Setup
```bash
cd billguard-ai/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
In another terminal: `cd billguard-ai/backend && python -c 'from app.database import init_db,SessionLocal; from scripts.seed_data import seed_database; init_db(); seed_database(SessionLocal())'`.

## API
`GET /health`, `/customers`, `/contracts`, `/invoices`, `/usage`, `/payments`, `/leakage-cases`, `/leakage-cases/{id}`, `/recovery-actions`, `/audit-events`, `/dashboard/metrics`; `POST /seed`; `POST /engine/analyze`.

Typical flow: `curl -X POST http://127.0.0.1:8000/seed`, then `curl -X POST http://127.0.0.1:8000/engine/analyze`, then `curl http://127.0.0.1:8000/dashboard/metrics`.

Example health: `{"status":"ok","service":"billguard-ai"}`. Example analyze: `{"cases_created":1,"potential_leakage":"54000.00"}` (counts vary by scenario implementation). Metrics expose expected, invoiced, potential, validated, recoverable, and recovered amounts; the latter are zero unless persisted evidence exists.

## Tests
From `backend`: `pytest -q`.

## Prototype limitations
No authentication, AI agent, payment gateway, WhatsApp, production migrations, or real customer data. The usage generator is intentionally large and SQLite is for demo use only. All detected records require future human/AI investigation and approval before outreach.
