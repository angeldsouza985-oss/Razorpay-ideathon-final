# BillGuard AI

**AI-powered revenue leakage detection, investigation, governance, and recovery orchestration for B2B billing.**

BillGuard AI identifies revenue that a billing system failed to capture by comparing **contracts, amendments, usage, invoices, and payments**. It combines deterministic financial calculations with evidence-grounded AI investigation and a human-governed recovery workflow.

## What BillGuard Does

```text
Contract + Usage + Invoice + Payment
                ↓
      Deterministic Revenue Engine
                ↓
       Potential Leakage Cases
                ↓
          Evidence Collection
                ↓
        AI Investigation Layer
                ↓
     Confirmed / Exception / Unclear
                ↓
       Recovery Recommendation
                ↓
       Governance & Risk Check
                ↓
          Human Approval
                ↓
       Simulated Recovery
                ↓
          Complete Audit Trail
```

### Core principle

**AI does not control financial truth.**

The deterministic revenue engine calculates expected billing amounts. The AI layer interprets the supplied evidence and explains the likely root cause. Recovery actions remain subject to governance and human approval.

---

## Key Features

### 1. Deterministic Leakage Detection

Compares:

* Contract pricing
* Discounts
* Price escalations
* Usage and overage
* Amendments
* Service charges
* Taxes
* Invoice totals
* Payment status

Financial calculations use Python `Decimal` rather than floating-point arithmetic.

### 2. Evidence-Grounded AI Investigation

The investigation service sends the collected evidence package to the configured AI provider.

The model is explicitly instructed to:

* Use only supplied evidence
* Avoid inventing financial values
* Preserve deterministic calculations
* Explain the root cause
* Classify the case
* Recommend an action
* Never approve or execute recovery

If the AI provider is unavailable, BillGuard falls back to a deterministic investigation path.

### 3. Recovery Strategy

Confirmed leakage can produce a recovery recommendation such as:

```text
GENERATE_ADJUSTMENT_INVOICE
```

The recommendation includes:

* Expected recovery
* Intervention cost
* Approval requirement
* Governance decision
* Governance reason

### 4. Human-in-the-Loop Governance

Recovery above the configured approval threshold requires human approval.

For example:

```text
Recovery: ₹54,000
Approval threshold: ₹25,000
Decision: HUMAN_REVIEW
```

The system therefore does not allow the AI to autonomously recover money.

### 5. Simulated Recovery

After approval, BillGuard can simulate the recovery workflow and generate a simulated adjustment identifier.

Example:

```text
Status: RECOVERED
Recovered amount: ₹54,000
Simulated invoice: SIM-XXXXXXXXXXXX
```

No real financial transaction is performed.

### 6. Full Audit Trail

The system records important events including:

* CASE_CREATED
* EVIDENCE_COLLECTED
* INVESTIGATION_STARTED
* AI_INVESTIGATION_STARTED
* AI_INVESTIGATION_COMPLETED
* LEAKAGE_CONFIRMED
* RECOVERY_RECOMMENDED
* GOVERNANCE_CHECKED
* APPROVAL_REQUESTED
* RECOVERY_APPROVED
* RECOVERY_EXECUTED

This provides traceability from detection through recovery.

---

## Architecture

### Backend

* Python
* FastAPI
* SQLAlchemy
* SQLite
* Pydantic
* Deterministic revenue engine
* Evidence collection service
* AI investigation service
* Recovery strategy
* Governance engine
* Audit logging

### Frontend

* Next.js
* React
* TypeScript
* Tailwind CSS
* shadcn/ui components

### AI

The AI integration is provider-configurable through environment variables.

Default configuration:

```env
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1
AI_PROVIDER=openai
```

The API key is intentionally excluded from version control.

---

## Local Setup

### Backend

From the project root:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

The API will run at:

```text
http://127.0.0.1:8000
```

Swagger documentation:

```text
http://127.0.0.1:8000/docs
```

### Environment variables

Create:

```text
backend/.env
```

Example:

```env
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
OPENAI_BASE_URL=https://api.openai.com/v1
AI_PROVIDER=openai
```

**Never commit the actual API key.**

A safe template is provided as:

```text
backend/.env.example
```

---

## Demo Flow

### 1. Seed synthetic billing data

```http
POST /seed
```

Example:

```json
{
  "status": "seeded",
  "customers": 100,
  "invoices": 1200,
  "usage_records": 120000
}
```

### 2. Run the deterministic leakage engine

```http
POST /engine/analyze
```

Example:

```json
{
  "cases_created": 1089,
  "potential_leakage": "3637750.00"
}
```

### 3. List leakage cases

```http
GET /leakage-cases
```

### 4. Investigate a case

```http
POST /leakage-cases/{case_id}/investigate
```

The investigation returns:

* Classification
* Root cause
* Investigation summary
* Reasoning
* Evidence
* Confidence
* Recoverability
* Recommended action

### 5. Review the audit trail

```http
GET /leakage-cases/{case_id}/audit
```

### 6. Generate a recovery recommendation

```http
POST /leakage-cases/{case_id}/recommend-recovery
```

### 7. Approve recovery

```http
POST /leakage-cases/{case_id}/approve-recovery
```

Cases exceeding the governance threshold require explicit human approval.

### 8. Execute simulated recovery

```http
POST /leakage-cases/{case_id}/recover
```

The recovery is simulated and does not perform a real financial transaction.

---

## Example Investigation

A detected case can contain evidence such as:

```text
Contract base price: ₹50,000
Included usage: 100,000 API calls
Actual usage: 178,000 API calls
Overage rate: ₹0.50/API call
Actual invoice: ₹40,000
Expected invoice: ₹94,000
Potential leakage: ₹54,000
```

BillGuard can classify this as confirmed leakage, explain the evidence, recommend an adjustment invoice, and route the recovery through governance.

For a ₹54,000 recovery with a ₹25,000 approval threshold:

```text
Governance decision: HUMAN_REVIEW
Approval required: true
```

After explicit approval:

```text
Status: APPROVED
        ↓
Simulated recovery
        ↓
Status: RECOVERED
```

Every step is recorded in the audit trail.

---

## Testing

From the backend directory:

```powershell
python -m pytest -q
```

The current test suite covers the core seed, revenue, investigation, recovery, governance, and endpoint workflows.

---

## Security & Data Handling

The project is a hackathon prototype.

* No real customer data is used.
* API keys are stored in local environment variables.
* `.env` is excluded from Git.
* Recovery execution is simulated.
* AI cannot directly authorize financial recovery.
* SQLite is used for demonstration purposes.

---

## Prototype Limitations

This prototype does not yet provide:

* Production authentication
* Production database migrations
* Real payment gateway execution
* Real adjustment invoice creation
* WhatsApp/customer outreach
* Production-scale infrastructure
* Enterprise identity and access management

The recovery layer intentionally remains simulated for safety.

---

## Why BillGuard AI?

Traditional billing systems can correctly process invoices while still missing revenue caused by:

* Unbilled usage
* Incorrect rates
* Missed price escalations
* Contract amendments
* Discount errors
* Service charge discrepancies
* Other contract-to-invoice mismatches

BillGuard approaches the problem as an **evidence and recovery pipeline**, not simply as an anomaly detector.

The goal is to move from:

**"Something looks wrong."**

to:

**"Here is the evidence, here is the deterministic financial difference, here is the explanation, here is the recovery recommendation, here is the governance decision, and here is the complete audit trail."**
