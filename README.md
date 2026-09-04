# BillGuard AI

<p align="center">
  <strong>Find revenue that's slipping away — and win it back.</strong>
</p>

<p align="center">
  AI-powered revenue intelligence and bounded recovery for billing leakage.
</p>

<p align="center">
  <a href="https://razorpay-ideathon-final.vercel.app/">🚀 Live Demo</a>
  &nbsp;•&nbsp;
  <a href="https://github.com/angeldsouza985-oss/Razorpay-ideathon-final">💻 GitHub</a>
</p>

---

## 🚨 The Problem

Revenue leakage rarely comes from one obvious failure.

It hides in the gaps between:

- Contracts and actual usage
- Usage and invoices
- Contract amendments and billing
- Expected revenue and invoiced revenue
- Billing events and recovery actions

A billing system can tell you **what was invoiced**.

It doesn't necessarily tell you:

> **What should have been invoiced, why the difference happened, whether the difference is legitimate, and what should safely happen next.**

When this analysis is manual, revenue leakage can remain invisible across hundreds or thousands of customers.

And detection alone isn't enough.

The real problem is:

**Detect → Investigate → Decide → Recover → Measure**

---

# 💡 Introducing BillGuard AI

**BillGuard AI** is an AI-powered revenue recovery agent built for the **Razorpay AI Buildathon — AI Revenue Recovery** challenge.

BillGuard turns billing discrepancies into a controlled recovery workflow.

It:

1. Detects revenue at risk
2. Collects the supporting evidence
3. Investigates the discrepancy
4. Classifies the case
5. Determines the appropriate intervention
6. Applies recovery policies
7. Escalates cases when human approval is required
8. Executes bounded recovery actions
9. Records the complete audit trail
10. Measures recovered revenue

### The core principle

> **AI interprets evidence.  
> The system owns financial truth.  
> Policies own authority.  
> Audit owns accountability.**

---

# 🚀 Live Product

## BillGuard AI Control Center

The deployed application provides a centralized revenue recovery control center with:

- Dashboard
- Leakage Cases
- AI Investigation
- Recovery Queue
- Audit Trail
- System status
- Revenue protection metrics

### Live Demo

**https://razorpay-ideathon-final.vercel.app/**

The deployed frontend communicates with the FastAPI revenue engine and exposes the complete recovery lifecycle.

---

# ⚙️ The Agentic Workflow

BillGuard follows a five-stage autonomous recovery pipeline:

```text
┌──────────────┐
│    DETECT    │
│              │
│ Contract vs  │
│ Invoice      │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│    COLLECT   │
│              │
│ Evidence     │
│ Package      │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ INVESTIGATE  │
│              │
│ AI +         │
│ Deterministic│
│ Facts        │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│    GOVERN    │
│              │
│ Policy +     │
│ Human Review │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   RECOVER    │
│              │
│ Bounded      │
│ Adjustment   │
└──────────────┘
