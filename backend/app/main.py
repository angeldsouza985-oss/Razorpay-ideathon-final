from decimal import Decimal
import json

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import os
from .database import init_db, get_db
from .models.entities import *
from .engines.revenue_engine import calculate_expected, D
from .services.investigation import (
    collect_evidence,
    serialize_evidence,
    investigate_case,
    recommend,
    execute,
)


app = FastAPI(
    title="BillGuard AI API",
    version="0.2.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
def startup():
    init_db()


# ============================================================
# SERIALIZATION
# ============================================================

def serialize(obj):
    return {
        c.name: (
            str(getattr(obj, c.name))
            if isinstance(getattr(obj, c.name), Decimal)
            else getattr(obj, c.name)
        )
        for c in obj.__table__.columns
    }


def listing(model):
    def route(db: Session = Depends(get_db)):
        return [
            serialize(x)
            for x in db.query(model).all()
        ]

    return route


# ============================================================
# BASIC LISTING ENDPOINTS
# ============================================================

for path, model in [
    ("customers", Customer),
    ("contracts", Contract),
    ("invoices", Invoice),
    ("usage", UsageRecord),
    ("payments", Payment),
    ("recovery-actions", RecoveryAction),
    ("audit-events", AuditEvent),
]:
    app.get("/" + path)(listing(model))


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "billguard-ai",
    }


# ============================================================
# LEAKAGE CASES
# ============================================================

@app.get("/leakage-cases")
def cases(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: str | None = None,
    leakage_type: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(LeakageCase)

    if status:
        query = query.filter(
            LeakageCase.status == status
        )

    if leakage_type:
        query = query.filter(
            LeakageCase.leakage_type == leakage_type
        )

    return {
        "total": query.count(),
        "limit": limit,
        "offset": offset,
        "cases": [
            serialize(x)
            for x in (
                query
                .order_by(LeakageCase.id)
                .offset(offset)
                .limit(limit)
                .all()
            )
        ],
    }


# ============================================================
# CASE DETAIL
# ============================================================

def _case_detail(db: Session, x: LeakageCase):

    customer = db.get(
        Customer,
        x.customer_id
    )

    contract = db.get(
        Contract,
        x.contract_id
    )

    invoice = db.get(
        Invoice,
        x.invoice_id
    )

    usage = (
        db.query(UsageRecord)
        .filter_by(contract_id=x.contract_id)
        .filter(
            UsageRecord.period_start
            >= invoice.billing_period_start,
            UsageRecord.period_end
            <= invoice.billing_period_end,
        )
        .all()
        if invoice
        else []
    )

    payments = (
        db.query(Payment)
        .filter_by(invoice_id=x.invoice_id)
        .all()
    )

    amendments = (
        db.query(ContractAmendment)
        .filter_by(contract_id=x.contract_id)
        .order_by(
            ContractAmendment.amendment_date
        )
        .all()
    )

    actions = (
        db.query(RecoveryAction)
        .filter_by(leakage_case_id=x.id)
        .order_by(RecoveryAction.id)
        .all()
    )

    audit_events = (
        db.query(AuditEvent)
        .filter_by(leakage_case_id=x.id)
        .order_by(AuditEvent.timestamp)
        .all()
    )

    return {
        "case": serialize(x),

        "customer": (
            serialize(customer)
            if customer
            else None
        ),

        "contract": (
            serialize(contract)
            if contract
            else None
        ),

        "invoice": (
            serialize(invoice)
            if invoice
            else None
        ),

        "usage": [
            serialize(v)
            for v in usage
        ],

        "payments": [
            serialize(p)
            for p in payments
        ],

        "amendments": [
            serialize(a)
            for a in amendments
        ],

        "investigation": {
            "classification": x.classification,
            "root_cause": x.root_cause,
            "summary": x.investigation_summary,
            "reasoning": x.reasoning,
            "evidence": x.evidence,
            "investigated_at": (
                x.investigated_at.isoformat()
                if x.investigated_at
                else None
            ),
        },

        "recovery": {
            "actions": [
                serialize(a)
                for a in actions
            ],
            "recovered_amount": str(
                x.recovered_amount
            ),
        },

        "audit_events": [
            serialize(e)
            for e in audit_events
        ],
    }


@app.get("/leakage-cases/{case_id}")
def case(
    case_id: int,
    db: Session = Depends(get_db),
):
    x = db.get(
        LeakageCase,
        case_id
    )

    if not x:
        raise HTTPException(
            404,
            "Leakage case not found"
        )

    return _case_detail(db, x)


# ============================================================
# SEED DATABASE
# ============================================================

@app.post("/seed")
def seed(
    db: Session = Depends(get_db),
):
    from scripts.seed_data import seed_database

    seed_database(db)

    return {
        "status": "seeded",
        "customers": db.query(Customer).count(),
        "invoices": db.query(Invoice).count(),
        "usage_records": db.query(UsageRecord).count(),
    }


# ============================================================
# DETERMINISTIC REVENUE ANALYSIS
# ============================================================

@app.post("/engine/analyze")
def analyze(
    db: Session = Depends(get_db),
):

    created = []

    for inv in db.query(Invoice).all():

        # Idempotency:
        # Do not create another case for an invoice
        # that has already been analyzed.
        if (
            db.query(LeakageCase)
            .filter_by(invoice_id=inv.id)
            .first()
        ):
            continue

        c = db.get(
            Contract,
            inv.contract_id
        )

        u = (
            db.query(UsageRecord)
            .filter_by(contract_id=c.id)
            .all()
        )

        a = (
            db.query(ContractAmendment)
            .filter_by(contract_id=c.id)
            .all()
        )

        e = calculate_expected(
            c,
            inv.billing_period_start,
            inv.billing_period_end,
            u,
            a,
            inv,
        )

        diff = (
            e["expected_total"]
            - D(inv.total_amount)
        )

        if diff > 0:

            typ = (
                "UNBILLED_USAGE"
                if e["expected_usage_amount"]
                > D(inv.usage_amount)

                else "MISSED_PRICE_ESCALATION"
                if e["expected_base_amount"]
                > D(inv.base_amount)

                else "CONTRACT_AMENDMENT_MISMATCH"
            )

            x = LeakageCase(
                customer_id=inv.customer_id,
                contract_id=inv.contract_id,
                invoice_id=inv.id,

                leakage_type=typ,

                expected_amount=e[
                    "expected_total"
                ],

                actual_amount=D(
                    inv.total_amount
                ),

                leakage_amount=diff,

                confidence=Decimal(".75"),

                recoverability=Decimal(".50"),

                recommended_action=(
                    "GENERATE_ADJUSTMENT_INVOICE"
                ),

                status="POTENTIAL LEAKAGE",
            )

            db.add(x)
            db.flush()

            db.add(
                AuditEvent(
                    leakage_case_id=x.id,
                    event_type="CASE_CREATED",
                    actor="deterministic-engine",
                    description=(
                        "Potential leakage detected; "
                        "requires investigation."
                    ),
                    evidence=str({
                        k: str(v)
                        for k, v in e.items()
                    }),
                    result="POTENTIAL LEAKAGE",
                )
            )

            created.append(x)

    db.commit()

    return {
        "cases_created": len(created),
        "potential_leakage": str(
            sum(
                (
                    D(x.leakage_amount)
                    for x in created
                ),
                Decimal(0),
            )
        ),
    }


# ============================================================
# INVESTIGATION
# ============================================================

@app.get(
    "/leakage-cases/{case_id}/investigation"
)
def get_investigation(
    case_id: int,
    db: Session = Depends(get_db),
):

    c = db.get(
        LeakageCase,
        case_id
    )

    if not c or not c.investigated_at:
        raise HTTPException(
            404,
            "Investigation not found"
        )

    return (
        serialize(c)
        | {
            "evidence_package":
                serialize_evidence(
                    collect_evidence(
                        db,
                        case_id
                    )
                )
        }
    )


@app.post(
    "/leakage-cases/{case_id}/investigate"
)
def investigation(
    case_id: int,
    db: Session = Depends(get_db),
):

    try:
        c = investigate_case(
            db,
            case_id
        )

    except ValueError as e:
        raise HTTPException(
            404,
            str(e)
        )

    return (
        serialize(c)
        | {
            "evidence_package":
                serialize_evidence(
                    collect_evidence(
                        db,
                        case_id
                    )
                )
        }
    )


# ============================================================
# RECOVERY RECOMMENDATION
# ============================================================

@app.post(
    "/leakage-cases/{case_id}/recommend-recovery"
)
def recovery_recommendation(
    case_id: int,
    db: Session = Depends(get_db),
):

    try:
        a, d, r = recommend(
            db,
            case_id
        )

    except ValueError as e:
        raise HTTPException(
            404,
            str(e)
        )

    return (
        serialize(a)
        | {
            "governance_decision": d,
            "governance_reason": r,
        }
    )


# ============================================================
# RECOVERY QUEUE
# ============================================================

@app.get("/recovery-queue")
def queue(
    db: Session = Depends(get_db),
):

    rows = []

    for c in (
        db.query(LeakageCase)
        .filter(
            LeakageCase.classification
            == "CONFIRMED_LEAKAGE"
        )
        .all()
    ):

        a = (
            db.query(RecoveryAction)
            .filter_by(
                leakage_case_id=c.id
            )
            .first()
        )

        if a:

            priority = (
                D(a.expected_recovery)
                * D(c.confidence)
                / max(
                    D(a.intervention_cost),
                    Decimal("1")
                )
            )

            rows.append(
                (
                    priority,
                    serialize(c)
                    | {
                        "priority_score":
                            str(priority)
                    },
                )
            )

    return [
        x[1]
        for x in sorted(
            rows,
            key=lambda x: x[0],
            reverse=True,
        )
    ]


# ============================================================
# RECOVERY ACTION
# ============================================================

@app.get(
    "/recovery-actions/{action_id}"
)
def action(
    action_id: int,
    db: Session = Depends(get_db),
):

    x = db.get(
        RecoveryAction,
        action_id
    )

    if not x:
        raise HTTPException(
            404,
            "Recovery action not found"
        )

    return serialize(x)


# ============================================================
# APPROVE RECOVERY ACTION
# ============================================================

@app.post(
    "/recovery-actions/{action_id}/approve"
)
def approve(
    action_id: int,
    db: Session = Depends(get_db),
):

    a = db.get(
        RecoveryAction,
        action_id
    )

    if (
        not a
        or a.status != "PENDING_APPROVAL"
    ):
        raise HTTPException(
            400,
            "Action is not pending approval"
        )

    c = db.get(
        LeakageCase,
        a.leakage_case_id
    )

    a.status = "APPROVED"
    c.status = "APPROVED"

    db.add(
        AuditEvent(
            leakage_case_id=c.id,
            event_type="RECOVERY_APPROVED",
            actor="finance-approver",
            description=(
                "Authorized human approved "
                "simulated recovery."
            ),
            evidence=json.dumps(
                {
                    "amount":
                        str(a.expected_recovery),

                    "action":
                        a.action_type,

                    "previous_status":
                        "PENDING_APPROVAL",

                    "new_status":
                        "APPROVED",
                }
            ),
            result="APPROVED",
        )
    )

    db.commit()

    return (
        serialize(a)
        | {
            "case_id": c.id,
            "status": "APPROVED",
        }
    )


@app.post(
    "/leakage-cases/{case_id}/approve-recovery"
)
def approve_case(
    case_id: int,
    db: Session = Depends(get_db),
):

    a = (
        db.query(RecoveryAction)
        .filter_by(
            leakage_case_id=case_id
        )
        .order_by(
            RecoveryAction.id.desc()
        )
        .first()
    )

    if not a:
        raise HTTPException(
            404,
            "Recovery recommendation not found"
        )

    return approve(
        a.id,
        db
    )


# ============================================================
# REJECT RECOVERY
# ============================================================

@app.post(
    "/leakage-cases/{case_id}/reject-recovery"
)
def reject_case(
    case_id: int,
    db: Session = Depends(get_db),
):

    a = (
        db.query(RecoveryAction)
        .filter_by(
            leakage_case_id=case_id
        )
        .order_by(
            RecoveryAction.id.desc()
        )
        .first()
    )

    if not a:
        raise HTTPException(
            404,
            "Recovery recommendation not found"
        )

    if a.status == "REJECTED":
        raise HTTPException(
            409,
            "Recovery already rejected"
        )

    c = db.get(
        LeakageCase,
        case_id
    )

    previous = a.status

    a.status = "REJECTED"
    c.status = "REJECTED"
    c.recovered_amount = Decimal("0")

    db.add(
        AuditEvent(
            leakage_case_id=case_id,
            event_type="RECOVERY_REJECTED",
            actor="finance-approver",
            description="Recovery rejected.",
            evidence=json.dumps(
                {
                    "previous_status":
                        previous,

                    "new_status":
                        "REJECTED",
                }
            ),
            result="REJECTED",
        )
    )

    db.commit()

    return (
        serialize(a)
        | {
            "case_id": case_id,
            "status": "REJECTED",
        }
    )


# ============================================================
# EXECUTE RECOVERY
# ============================================================

@app.post(
    "/leakage-cases/{case_id}/recover"
)
def recover_case(
    case_id: int,
    db: Session = Depends(get_db),
):

    a = (
        db.query(RecoveryAction)
        .filter_by(
            leakage_case_id=case_id
        )
        .order_by(
            RecoveryAction.id.desc()
        )
        .first()
    )

    if not a:
        raise HTTPException(
            404,
            "Recovery recommendation not found"
        )

    case_obj = db.get(
        LeakageCase,
        case_id
    )

    if (
        a.status == "EXECUTED"
        or case_obj.status == "RECOVERED"
    ):
        raise HTTPException(
            409,
            "Recovery already executed for this case"
        )

    try:

        result, simulated_id = execute(
            db,
            a,
            "recovery-executor"
        )

    except ValueError as e:

        if "already executed" in str(e):
            raise HTTPException(
                409,
                str(e)
            )

        raise HTTPException(
            400,
            str(e)
        )

    c = db.get(
        LeakageCase,
        case_id
    )

    return {
        "case_id": case_id,
        "status": c.status,
        "recovered_amount":
            str(c.recovered_amount),
        "simulated_invoice_id":
            simulated_id,
        "message":
            "Recovery simulated successfully.",
    }


# ============================================================
# REJECT RECOVERY ACTION
# ============================================================

@app.post(
    "/recovery-actions/{action_id}/reject"
)
def reject(
    action_id: int,
    db: Session = Depends(get_db),
):

    a = db.get(
        RecoveryAction,
        action_id
    )

    if not a:
        raise HTTPException(
            404,
            "Recovery action not found"
        )

    a.status = "REJECTED"

    c = db.get(
        LeakageCase,
        a.leakage_case_id
    )

    c.status = "STOPPED"

    db.add(
        AuditEvent(
            leakage_case_id=c.id,
            event_type="REJECTED",
            actor="finance-approver",
            description="Recovery rejected.",
            evidence="",
            result="STOPPED",
        )
    )

    db.commit()

    return serialize(a)


# ============================================================
# AUDIT TRAIL
# ============================================================

@app.get(
    "/leakage-cases/{case_id}/audit"
)
def audit(
    case_id: int,
    db: Session = Depends(get_db),
):

    return [
        serialize(x)
        for x in (
            db.query(AuditEvent)
            .filter_by(
                leakage_case_id=case_id
            )
            .all()
        )
    ]


# ============================================================
# BATCH RECOVERY
# ============================================================

@app.post("/recovery/run-batch")
def batch(
    db: Session = Depends(get_db),
):

    scanned = 0
    confirmed = 0
    rejected = 0
    stopped = 0
    review = 0

    recoverable = Decimal(0)
    recovered = Decimal(0)

    for c in (
        db.query(LeakageCase)
        .filter(
            LeakageCase.status
            == "POTENTIAL LEAKAGE"
        )
        .all()
    ):

        scanned += 1

        c = investigate_case(
            db,
            c.id
        )

        confirmed += (
            c.classification
            == "CONFIRMED_LEAKAGE"
        )

        rejected += (
            c.classification
            != "CONFIRMED_LEAKAGE"
        )

        a, d, _ = recommend(
            db,
            c.id
        )

        if (
            c.classification
            == "CONFIRMED_LEAKAGE"
        ):
            recoverable += D(
                a.expected_recovery
            )

        if d == "HUMAN_REVIEW":
            review += 1

        if d == "STOP":
            stopped += 1

        if d == "AUTO_APPROVE":

            _, _ = execute(
                db,
                a
            )

            recovered += D(
                a.expected_recovery
            )

    return {
        "cases_scanned": scanned,
        "cases_confirmed": confirmed,
        "cases_rejected": rejected,
        "cases_stopped": stopped,
        "human_review": review,
        "recoverable_revenue":
            str(recoverable),
        "recovered_revenue":
            str(recovered),
    }


# ============================================================
# DASHBOARD METRICS
# ============================================================

@app.get("/dashboard/metrics")
def metrics(
    db: Session = Depends(get_db),
):

    invs = db.query(Invoice).all()
    cases = db.query(LeakageCase).all()

    expected = Decimal(0)

    for i in invs:

        c = db.get(
            Contract,
            i.contract_id
        )

        u = (
            db.query(UsageRecord)
            .filter_by(
                contract_id=c.id
            )
            .all()
        )

        a = (
            db.query(ContractAmendment)
            .filter_by(
                contract_id=c.id
            )
            .all()
        )

        expected += calculate_expected(
            c,
            i.billing_period_start,
            i.billing_period_end,
            u,
            a,
            i,
        )["expected_total"]

    # --------------------------------------------------------
    # Total potential leakage
    # --------------------------------------------------------

    potential = sum(
        (
            D(c.leakage_amount)
            for c in cases
        ),
        Decimal(0),
    )

    # --------------------------------------------------------
    # Total recovered revenue
    # --------------------------------------------------------

    recovered = sum(
        (
            D(c.recovered_amount)
            for c in cases
        ),
        Decimal(0),
    )

    # --------------------------------------------------------
    # Confirmed leakage cases
    # --------------------------------------------------------

    confirmed = [
        c
        for c in cases
        if c.classification
        == "CONFIRMED_LEAKAGE"
    ]

    validated_leakage = sum(
        (
            D(c.leakage_amount)
            for c in confirmed
        ),
        Decimal(0),
    )

    # --------------------------------------------------------
    # FIX:
    #
    # Only cases that are ACTUALLY waiting for approval
    # should be counted as human-review cases.
    #
    # Previously, confirmed cases above G�25,000 were also
    # counted even after they had already been approved or
    # recovered.
    # --------------------------------------------------------

    human_review_cases = sum(
        c.status == "RECOVERY_PENDING"
        for c in cases
    )

    # --------------------------------------------------------
    # Recovery rate
    # --------------------------------------------------------

    recovery_rate = (
        (
            recovered
            / sum(
                (
                    D(c.leakage_amount)
                    for c in confirmed
                ),
                Decimal(1),
            )
            * 100
        )
        .quantize(
            Decimal(".01")
        )
    )

    # --------------------------------------------------------
    # Final dashboard response
    # --------------------------------------------------------

    return {
        "total_revenue_expected":
            str(expected),

        "total_revenue_invoiced":
            str(
                sum(
                    (
                        D(i.total_amount)
                        for i in invs
                    ),
                    Decimal(0),
                )
            ),

        "potential_leakage":
            str(potential),

        "validated_leakage":
            str(validated_leakage),

        "recoverable_revenue":
            str(validated_leakage),

        "recovered_revenue":
            str(recovered),

        "total_cases":
            len(cases),

        "confirmed_cases":
            len(confirmed),

        "legitimate_cases":
            sum(
                c.classification
                == "LEGITIMATE_EXCEPTION"
                for c in cases
            ),

        "human_review_cases":
            human_review_cases,

        "stopped_cases":
            sum(
                c.status == "STOPPED"
                for c in cases
            ),

        "recovery_rate":
            str(recovery_rate),
    }


# ============================================================
# FULL DASHBOARD
# ============================================================

@app.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
):

    # Reuse the exact same metrics calculation.
    dashboard_data = metrics(db)

    # Get first 20 leakage cases.
    case_rows = (
        db.query(LeakageCase)
        .order_by(LeakageCase.id)
        .limit(20)
        .all()
    )

    return {
        "metrics": dashboard_data,

        "cases": [
            serialize(c)
            for c in case_rows
        ],
    }
