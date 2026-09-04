BillGuard AI

Find revenue at risk. Win it back.

BillGuard AI is an AI-powered revenue recovery prototype for B2B billing operations.

It detects discrepancies between what a customer should have been billed and what was actually invoiced, investigates the evidence, applies bounded recovery policies, and executes a controlled recovery workflow when the case is eligible.

Core workflow: Detect → Collect Evidence → Investigate → Govern → Recover → Audit

Why BillGuard?

Revenue leakage is often hidden inside operational handoffs:

contract terms change but billing does not

customer usage exceeds what was invoiced

price escalations are missed

billing exceptions are not handled correctly

recoverable value remains unresolved

A simple anomaly detector is not enough. Teams still need to establish whether the discrepancy is real, decide what action is permitted, execute that action, and maintain an audit trail.

BillGuard closes that loop.

What the Prototype Does

1. Detect

BillGuard compares:

Contracts

Usage records

Contract amendments

Invoices

Payments

It calculates expected revenue versus invoiced revenue and creates leakage cases when a meaningful discrepancy is detected.

2. Investigate

Each case becomes an evidence package.

The AI investigation layer produces a structured interpretation containing:

classification

rationale

recommended recovery action

evidence-aware explanation

The AI is used for interpretation and recommendation; it does not own the system's financial truth.

3. Govern

Recovery recommendations pass through deterministic policy controls.

Outcome

Meaning

AUTO_APPROVE

Evidence and economics satisfy the recovery policy

HUMAN_REVIEW

The case exceeds automatic authority or needs human judgment

STOP

Evidence is insufficient or the recovery path is invalid

This creates bounded automation instead of unrestricted financial actions.

4. Recover

For an eligible case, BillGuard executes a specific recovery action.

In the current prototype this is represented by a simulated recovery invoice, followed by an updated case status and recovery metrics.

5. Audit

The workflow records the decision chain:

evidence → investigation → policy decision → recovery action → outcome

This makes the recovery path traceable and reviewable.

Architecture

                 ┌─────────────────────────┐
                 │ Contracts / Amendments   │
                 │ Usage / Invoices         │
                 │ Payments                 │
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │ Revenue Detection Engine │
                 │ Expected vs Invoiced     │
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │ Leakage Case             │
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │ AI Investigation         │
                 │ Classification + Rationale│
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │ Deterministic Governance│
                 │ Auto / Human / Stop      │
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │ Bounded Recovery         │
                 │ + Audit Event            │
                 └─────────────────────────┘

Technology

Frontend

Next.js

React

TypeScript

Backend

Python

FastAPI

SQLAlchemy

Pydantic

Data

SQLite for the demo prototype

AI

OpenAI-compatible investigation service

Deterministic demo fallback when an API key is not configured

Deployment

Frontend: Vercel

Backend: Render

Demo Results

The current seeded prototype demonstrates:

Metric

Value

Leakage cases detected

12

Potential leakage

₹92,760

Demonstrated recovered revenue

₹2,500

Prototype recovery-rate metric

99.96%

Example recovery case

Customer: Vertex Labs India
Issue: Missed price escalation

Expected revenue      ₹26,250
Actually invoiced     ₹23,750
Revenue at risk        ₹2,500

The demonstrated workflow is:

Investigate
    ↓
CONFIRMED_LEAKAGE
    ↓
AUTO_APPROVE
    ↓
Recover
    ↓
₹2,500 recovered

Live Prototype

Production frontend:
https://billguard-kappa.vercel.app

Production API:
https://billguard-api-gb6a.onrender.com

The frontend communicates with the production FastAPI service.

Prototype note: the current Render deployment uses SQLite on the service filesystem. The demo dataset should therefore be treated as prototype/demo state rather than production-grade persistent storage.

Running Locally

Backend

From the backend directory:

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload

Backend:

http://127.0.0.1:8000

Seed the demo data

With the backend running:

Invoke-RestMethod -Uri "http://127.0.0.1:8000/seed" -Method POST

Then run detection:

Invoke-RestMethod -Uri "http://127.0.0.1:8000/engine/analyze" -Method POST

Frontend

From the project root:

npm install
npm run dev

Open:

http://localhost:3000

The frontend API endpoint can be configured through NEXT_PUBLIC_API_URL. The current demo build may also point directly to the production Render API.

API

Important endpoints:

GET  /dashboard/metrics
GET  /leakage-cases
GET  /leakage-cases/{id}

POST /seed
POST /engine/analyze
POST /leakage-cases/{id}/investigate
POST /leakage-cases/{id}/recommend-recovery
POST /leakage-cases/{id}/recover

When running locally, FastAPI documentation is available at:

http://127.0.0.1:8000/docs

AI and Safety Design

BillGuard deliberately separates reasoning from authority.

AI is responsible for

interpreting evidence

classifying leakage

explaining discrepancies

recommending an action

Deterministic application logic is responsible for

financial calculations

policy thresholds

approval requirements

stopping conditions

recovery execution

persistence and audit records

This lets the system use AI without giving the model unrestricted control over financial actions.

Project Structure

bill-guard-ai/
│
├── app/
│   └── page.tsx
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── database.py
│   │   ├── models/
│   │   └── services/
│   ├── scripts/
│   │   └── seed_data.py
│   ├── requirements.txt
│   └── .python-version
│
├── package.json
├── README.md
└── .gitignore

Testing

From the backend directory:

pytest -q

Prototype Boundaries

This is a hackathon/demo prototype, not a production billing platform.

Current limitations include:

SQLite is used for demo storage

authentication is not implemented

recovery actions are simulated rather than connected to a live payment/billing provider

the prototype uses seeded synthetic data

production-grade database migrations and persistent infrastructure are not included

The focus is the revenue-recovery agent workflow, bounded automation, governance, and auditability.

Why This Is Different

Traditional billing analytics can tell a team:

“Something looks wrong.”

BillGuard is designed to continue the workflow:

“Something looks wrong → here is the evidence → here is what it means → here is what policy allows → here is the recovery action → here is the audit trail.”

That is the core idea behind AI Revenue Recovery.

Challenge

Built as a prototype for the Razorpay AI Buildathon — AI Revenue Recovery track.

BillGuard AI

Detect. Investigate. Recover.
