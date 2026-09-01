from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import uuid4
import json

from sqlalchemy.orm import Session

from ..models.entities import *
from ..engines.revenue_engine import (
    calculate_expected,
    compare_invoice,
    D,
)
from .ai_service import AIService


# =========================================================
# CONSTANTS
# =========================================================

CLASSIFICATIONS = {
    "CONFIRMED_LEAKAGE",
    "LEGITIMATE_EXCEPTION",
    "INSUFFICIENT_EVIDENCE",
    "DISPUTED",
}

RECOVERY_ACTIONS = {
    "GENERATE_ADJUSTMENT_INVOICE",
    "CORRECT_FUTURE_BILLING",
    "REQUEST_CONTRACT_VERIFICATION",
    "REQUEST_FINANCE_REVIEW",
    "SEND_CUSTOMER_CLARIFICATION",
    "STOP",
}

AMENDMENT_FIELDS = {
    "base_monthly_price",
    "discount_percentage",
    "escalation_percentage",
    "service_charge",
    "overage_price",
    "included_usage",
}

HUMAN_REVIEW_THRESHOLD = Decimal("25000")
MIN_CONFIDENCE = Decimal("0.80")
INTERVENTION_COST = Decimal("1000")


# =========================================================
# EVIDENCE MODEL
# =========================================================

@dataclass
class Evidence:
    customer: Customer
    contract: Contract
    amendments: list
    invoice: Invoice
    usage: list
    payments: list
    expected: dict
    comparison: dict


# =========================================================
# AUDIT
# =========================================================

def audit(
    db,
    case_id,
    event,
    actor,
    description,
    evidence="",
    result="",
):
    db.add(
        AuditEvent(
            leakage_case_id=case_id,
            event_type=event,
            actor=actor,
            description=description,
            evidence=evidence,
            result=result,
        )
    )


# =========================================================
# EVIDENCE COLLECTION
# =========================================================

def collect_evidence(
    db: Session,
    case_id: int,
) -> Evidence:

    case = db.get(LeakageCase, case_id)

    if not case:
        raise ValueError("Leakage case not found")

    customer = db.get(Customer, case.customer_id)
    contract = db.get(Contract, case.contract_id)
    invoice = db.get(Invoice, case.invoice_id)

    if not customer or not contract or not invoice:
        raise ValueError(
            "Case references missing financial records"
        )

    amendments = (
        db.query(ContractAmendment)
        .filter_by(contract_id=contract.id)
        .order_by(ContractAmendment.amendment_date)
        .all()
    )

    usage = (
        db.query(UsageRecord)
        .filter(
            UsageRecord.contract_id == contract.id,
            UsageRecord.period_start <= invoice.billing_period_end,
            UsageRecord.period_end >= invoice.billing_period_start,
        )
        .all()
    )

    payments = (
        db.query(Payment)
        .filter_by(invoice_id=invoice.id)
        .all()
    )

    expected = calculate_expected(
        contract,
        invoice.billing_period_start,
        invoice.billing_period_end,
        usage,
        amendments,
        invoice,
    )

    comparison = compare_invoice(
        expected,
        invoice,
    )

    return Evidence(
        customer=customer,
        contract=contract,
        amendments=amendments,
        invoice=invoice,
        usage=usage,
        payments=payments,
        expected=expected,
        comparison=comparison,
    )


# =========================================================
# EVIDENCE ITEMS
# =========================================================

def evidence_items(e: Evidence):

    items = [
        {
            "source": "contract",
            "fact": (
                f"Base monthly price is ₹{e.contract.base_monthly_price}; "
                f"included usage is {e.contract.included_usage} "
                f"{e.contract.usage_unit}; "
                f"overage is ₹{e.contract.overage_price}/"
                f"{e.contract.usage_unit}."
            ),
        },
        {
            "source": "usage",
            "fact": (
                f"{sum((D(u.quantity) for u in e.usage), Decimal(0))} "
                f"{e.contract.usage_unit} recorded in the invoice period."
            ),
        },
        {
            "source": "invoice",
            "fact": (
                f"Invoice total is ₹{e.invoice.total_amount}."
            ),
        },
        {
            "source": "deterministic_engine",
            "fact": (
                f"Expected total is ₹{e.expected['expected_total']}; "
                f"actual total is ₹{e.comparison['actual_amount']}; "
                f"difference is ₹{e.comparison['difference']}."
            ),
        },
    ]

    for amendment in e.amendments:

        if amendment.approved:

            items.append(
                {
                    "source": "amendment",
                    "fact": (
                        f"Approved amendment dated "
                        f"{amendment.amendment_date}: "
                        f"{amendment.changed_field} changed "
                        f"from {amendment.old_value} "
                        f"to {amendment.new_value}."
                    ),
                }
            )

    for payment in e.payments:

        items.append(
            {
                "source": "payment",
                "fact": (
                    f"Payment of ₹{payment.amount} "
                    f"has status {payment.status}."
                ),
            }
        )

    return items


# =========================================================
# SERIALIZE EVIDENCE
# =========================================================

def serialize_evidence(e):

    return {
        "customer": {
            "id": e.customer.id,
            "name": e.customer.name,
        },

        "contract": {
            "id": e.contract.id,
            "contract_number": e.contract.contract_number,
        },

        "amendments": [
            {
                "id": a.id,
                "description": a.description,
                "approved": a.approved,
                "changed_field": a.changed_field,
                "old_value": a.old_value,
                "new_value": a.new_value,
            }
            for a in e.amendments
        ],

        "invoice": {
            "id": e.invoice.id,
            "total_amount": str(e.invoice.total_amount),
        },

        "usage": [
            {
                "quantity": str(u.quantity),
                "unit": u.unit,
            }
            for u in e.usage
        ],

        "payments": [
            {
                "amount": str(p.amount),
                "status": p.status,
            }
            for p in e.payments
        ],

        "expected_invoice": {
            k: str(v)
            for k, v in e.expected.items()
        },

        "difference": str(
            e.comparison["difference"]
        ),

        "evidence_items": evidence_items(e),
    }


# =========================================================
# DETERMINISTIC CLASSIFICATION
# =========================================================

def _deterministic_result(
    e: Evidence,
    case: LeakageCase,
):

    difference = D(
        e.comparison["difference"]
    )

    approved_amendments = [
        a
        for a in e.amendments
        if a.approved
        and a.amendment_date
        <= e.invoice.billing_period_end
    ]

    relevant_amendments = [
        a
        for a in approved_amendments
        if a.changed_field in AMENDMENT_FIELDS
    ]

    # -----------------------------------------------------
    # HARD DETERMINISTIC RULE
    #
    # If an approved amendment explains the commercial
    # terms, it must be considered before AI classification.
    # -----------------------------------------------------

    if difference <= 0:

        if relevant_amendments:

            classification = "LEGITIMATE_EXCEPTION"

            root_cause = (
                "The invoice is consistent with the "
                "deterministic contract calculation after "
                "applying an approved contractual amendment."
            )

            confidence = Decimal("0.95")

        else:

            classification = "INSUFFICIENT_EVIDENCE"

            root_cause = (
                "No positive deterministic billing variance "
                "was found."
            )

            confidence = Decimal("0.60")

    else:

        # Positive difference means the invoice is below
        # the deterministic expected amount.

        classification = "CONFIRMED_LEAKAGE"

        if case.leakage_type == "UNBILLED_USAGE":

            root_cause = (
                "Usage exceeded the contracted allowance "
                "and the invoice omitted the deterministic "
                "overage charge."
            )

        elif case.leakage_type == "MISSED_PRICE_ESCALATION":

            root_cause = (
                "The invoice used a lower base price than "
                "the contractual escalation calculation."
            )

        elif case.leakage_type == "EXPIRED_DISCOUNT":

            root_cause = (
                "The invoice applied a discount that was "
                "not applicable for the billing period."
            )

        elif case.leakage_type == "CONTRACT_AMENDMENT_MISMATCH":

            root_cause = (
                "The invoice differs from the commercial "
                "terms established by the applicable contract "
                "and amendments."
            )

        else:

            root_cause = (
                "The invoice is below the deterministic "
                "contract calculation."
            )

        confidence = Decimal("0.97")

    return {
        "classification": classification,

        "root_cause": root_cause,

        "investigation_summary": (
            "Deterministic comparison found "
            f"₹{difference} difference. "
            "Financial classification is governed by "
            "the deterministic billing engine."
        ),

        "reasoning": (
            "AI interpretation is constrained to the supplied "
            "evidence. Deterministic contract and invoice "
            "calculations remain authoritative."
        ),

        "confidence": confidence,

        "recoverability": (
            Decimal("0.90")
            if classification == "CONFIRMED_LEAKAGE"
            else Decimal("0")
        ),

        "recommended_action": (
            "GENERATE_ADJUSTMENT_INVOICE"
            if classification == "CONFIRMED_LEAKAGE"
            else "STOP"
        ),
    }


# =========================================================
# INVESTIGATION
# =========================================================

def investigate_case(
    db: Session,
    case_id: int,
):

    case = db.get(
        LeakageCase,
        case_id,
    )

    if not case:
        raise ValueError(
            "Leakage case not found"
        )

    # -----------------------------------------------------
    # IDEMPOTENCY
    # -----------------------------------------------------

    if (
        case.classification
        and case.investigated_at
    ):
        return case

    # -----------------------------------------------------
    # COLLECT EVIDENCE
    # -----------------------------------------------------

    e = collect_evidence(
        db,
        case_id,
    )

    items = evidence_items(e)

    audit(
        db,
        case_id,
        "EVIDENCE_COLLECTED",
        "evidence-collector",
        "Evidence package collected.",
        str(items),
        "READY",
    )

    audit(
        db,
        case_id,
        "INVESTIGATION_STARTED",
        "investigation-agent",
        "Investigation started.",
        str(items),
        "IN_PROGRESS",
    )

    # -----------------------------------------------------
    # AI INTERPRETATION
    # -----------------------------------------------------

    ai = AIService()

    package = {
        "case_type": case.leakage_type,

        "evidence": {
            "customer": {
                "id": e.customer.id,
                "name": e.customer.name,
            },

            "contract": {
                "id": e.contract.id,
                "contract_number": e.contract.contract_number,
            },

            "amendments": [
                {
                    "id": a.id,
                    "approved": a.approved,
                    "changed_field": a.changed_field,
                    "old_value": a.old_value,
                    "new_value": a.new_value,
                }
                for a in e.amendments
            ],

            "invoice": {
                "id": e.invoice.id,
                "total_amount": str(
                    e.invoice.total_amount
                ),
            },

            "usage": [
                {
                    "quantity": str(u.quantity),
                    "unit": u.unit,
                }
                for u in e.usage
            ],

            "payments": [
                {
                    "amount": str(p.amount),
                    "status": p.status,
                }
                for p in e.payments
            ],

            "expected_invoice": {
                k: str(v)
                for k, v in e.expected.items()
            },

            "difference": str(
                e.comparison["difference"]
            ),

            "evidence_items": items,
        },

        "expected_invoice": {
            k: str(v)
            for k, v in e.expected.items()
        },

        "comparison": {
            k: str(v)
            for k, v in e.comparison.items()
        },
    }

    # -----------------------------------------------------
    # AI CALL
    # -----------------------------------------------------

    audit(
        db,
        case_id,
        "AI_INVESTIGATION_STARTED",
        ai.provider,
        "AI investigation started.",
        json.dumps(ai.last_meta),
        "STARTED",
    )

    ai_result = ai.investigate(
        package
    )

    audit(
        db,
        case_id,
        "AI_INVESTIGATION_COMPLETED",
        ai.provider,
        "AI investigation completed.",
        json.dumps(ai.last_meta),
        ai_result.get(
            "classification",
            "INVALID",
        ),
    )

    # -----------------------------------------------------
    # IMPORTANT:
    #
    # AI IS NOT THE FINANCIAL AUTHORITY.
    #
    # Always derive the financial classification from the
    # deterministic contract/invoice calculation.
    # -----------------------------------------------------

    deterministic = _deterministic_result(
        e,
        case,
    )

    ai_classification = ai_result.get(
        "classification"
    )

    final_classification = deterministic[
        "classification"
    ]

    # -----------------------------------------------------
    # AUDIT AI / DETERMINISTIC AGREEMENT
    # -----------------------------------------------------

    if (
        ai_classification
        and ai_classification
        == final_classification
    ):

        audit(
            db,
            case_id,
            "AI_DETERMINISTIC_AGREEMENT",
            "investigation-agent",
            (
                "AI interpretation agrees with the "
                "deterministic financial classification."
            ),
            json.dumps(
                {
                    "ai_classification": ai_classification,
                    "deterministic_classification":
                        final_classification,
                }
            ),
            "AGREEMENT",
        )

    else:

        audit(
            db,
            case_id,
            "AI_DETERMINISTIC_CONFLICT",
            "investigation-agent",
            (
                "AI interpretation differed from the "
                "deterministic financial classification. "
                "Deterministic classification retained."
            ),
            json.dumps(
                {
                    "ai_classification": ai_classification,
                    "deterministic_classification":
                        final_classification,
                }
            ),
            "DETERMINISTIC_WINS",
        )

    # -----------------------------------------------------
    # APPLY DETERMINISTIC RESULT
    # -----------------------------------------------------

    case.classification = final_classification

    case.root_cause = deterministic[
        "root_cause"
    ]

    case.investigation_summary = deterministic[
        "investigation_summary"
    ]

    case.reasoning = deterministic[
        "reasoning"
    ]

    case.evidence = [
        {
            "source": x["source"],
            "fact": x["fact"],
        }
        for x in items
    ]

    case.investigated_at = datetime.utcnow()

    case.confidence = D(
        deterministic["confidence"]
    )

    case.recoverability = D(
        deterministic["recoverability"]
    )

    case.recommended_action = deterministic[
        "recommended_action"
    ]

    # -----------------------------------------------------
    # STATUS
    # -----------------------------------------------------

    if final_classification == "CONFIRMED_LEAKAGE":

        case.status = "CONFIRMED"

    elif final_classification == "LEGITIMATE_EXCEPTION":

        case.status = "LEGITIMATE"

    elif final_classification == "DISPUTED":

        case.status = "STOPPED"

    else:

        case.status = "STOPPED"

    # -----------------------------------------------------
    # AUDIT INVESTIGATION
    # -----------------------------------------------------

    audit(
        db,
        case_id,
        "INVESTIGATION_COMPLETED",
        "investigation-agent",
        case.investigation_summary,
        str(items),
        case.classification,
    )

    # -----------------------------------------------------
    # AUDIT CLASSIFICATION
    # -----------------------------------------------------

    if case.classification == "CONFIRMED_LEAKAGE":

        audit(
            db,
            case_id,
            "LEAKAGE_CONFIRMED",
            "investigation-agent",
            case.root_cause,
            str(items),
            case.classification,
        )

    else:

        audit(
            db,
            case_id,
            "LEAKAGE_REJECTED",
            "investigation-agent",
            case.root_cause,
            str(items),
            case.classification,
        )

    db.commit()

    return case


# =========================================================
# GOVERNANCE
# =========================================================

def governance(
    c,
    action,
    amendments=None,
):

    amount = D(
        action.expected_recovery
    )

    confidence = D(
        c.confidence
    )

    amendments = amendments or []

    # -----------------------------------------------------
    # DISPUTED CASE
    # -----------------------------------------------------

    if c.classification == "DISPUTED":

        return (
            "STOP",
            "Disputed cases cannot be recovered.",
            True,
        )

    # -----------------------------------------------------
    # ONLY CONFIRMED LEAKAGE CAN RECOVER
    # -----------------------------------------------------

    if c.classification != "CONFIRMED_LEAKAGE":

        return (
            "STOP",
            "Only confirmed leakage can be recovered.",
            True,
        )

    # -----------------------------------------------------
    # EVIDENCE GATE
    # -----------------------------------------------------

    if not c.evidence:

        return (
            "HUMAN_REVIEW",
            "Evidence is missing.",
            True,
        )

    # -----------------------------------------------------
    # APPROVED AMENDMENT GATE
    #
    # An approved amendment means the commercial terms
    # require explicit review before automated recovery.
    # -----------------------------------------------------

    conflicting_amendment = any(
        getattr(a, "approved", False)
        and getattr(a, "changed_field", "")
        in AMENDMENT_FIELDS
        for a in amendments
    )

    if conflicting_amendment:

        return (
            "HUMAN_REVIEW",
            (
                "An approved contractual amendment affects "
                "the billing terms. Commercial review is "
                "required before recovery."
            ),
            True,
        )

    # -----------------------------------------------------
    # CONFIDENCE GATE
    # -----------------------------------------------------

    if confidence < MIN_CONFIDENCE:

        return (
            "HUMAN_REVIEW",
            "Confidence is below 80%.",
            True,
        )

    # -----------------------------------------------------
    # HIGH VALUE GATE
    # -----------------------------------------------------

    if amount >= HUMAN_REVIEW_THRESHOLD:

        return (
            "HUMAN_REVIEW",
            (
                "Recovery exceeds ₹25,000 approval "
                "threshold."
            ),
            True,
        )

    # -----------------------------------------------------
    # ECONOMIC GATE
    # -----------------------------------------------------

    if amount <= D(
        action.intervention_cost
    ):

        return (
            "DO_NOT_PURSUE",
            (
                "Expected recovery does not exceed "
                "intervention cost."
            ),
            False,
        )

    # -----------------------------------------------------
    # SAFE AUTOMATIC APPROVAL
    # -----------------------------------------------------

    return (
        "AUTO_APPROVE",
        "Evidence and economics satisfy recovery policy.",
        False,
    )


# =========================================================
# RECOVERY RECOMMENDATION
# =========================================================

def recommend(
    db,
    case_id,
):

    c = db.get(
        LeakageCase,
        case_id,
    )

    if not c:

        raise ValueError(
            "Leakage case not found"
        )

    # -----------------------------------------------------
    # ENSURE INVESTIGATION EXISTS
    # -----------------------------------------------------

    if not c.classification:

        c = investigate_case(
            db,
            case_id,
        )

    # -----------------------------------------------------
    # IDEMPOTENCY
    # -----------------------------------------------------

    existing = (
        db.query(RecoveryAction)
        .filter_by(
            leakage_case_id=c.id
        )
        .order_by(
            RecoveryAction.id.desc()
        )
        .first()
    )

    if existing:

        if existing.status == "PENDING_APPROVAL":

            decision = "HUMAN_REVIEW"

        elif existing.status == "APPROVED":

            decision = "AUTO_APPROVE"

        elif existing.status == "STOPPED":

            decision = "STOP"

        elif existing.status == "REJECTED":

            decision = "STOP"

        elif existing.status == "EXECUTED":

            decision = "RECOVERED"

        else:

            decision = "UNKNOWN"

        return (
            existing,
            decision,
            existing.result
            or "Existing idempotent recovery action.",
        )

    # -----------------------------------------------------
    # CREATE ACTION
    # -----------------------------------------------------

    action = RecoveryAction(
        leakage_case_id=c.id,

        action_type=(
            c.recommended_action
        ),

        expected_recovery=(
            D(c.leakage_amount)
            if c.classification
            == "CONFIRMED_LEAKAGE"
            else Decimal("0")
        ),

        intervention_cost=(
            INTERVENTION_COST
        ),

        status="RECOMMENDED",
    )

    db.add(action)

    db.flush()

    # -----------------------------------------------------
    # EVIDENCE
    # -----------------------------------------------------

    evidence = collect_evidence(
        db,
        c.id,
    )

    # -----------------------------------------------------
    # GOVERNANCE
    # -----------------------------------------------------

    decision, reason, approval = governance(
        c,
        action,
        evidence.amendments,
    )

    action.approval_required = approval

    action.result = reason

    # -----------------------------------------------------
    # APPLY DECISION
    # -----------------------------------------------------

    if decision == "HUMAN_REVIEW":

        action.status = "PENDING_APPROVAL"

        c.status = "RECOVERY_PENDING"

    elif decision == "AUTO_APPROVE":

        action.status = "APPROVED"

        c.status = "APPROVED"

    else:

        action.status = "STOPPED"

        c.status = "STOPPED"

    # -----------------------------------------------------
    # AUDIT: RECOMMENDATION
    # -----------------------------------------------------

    audit(
        db,
        c.id,
        "RECOVERY_RECOMMENDED",
        "recovery-strategy",
        f"Recommended {action.action_type}.",
        str(c.evidence),
        decision,
    )

    # -----------------------------------------------------
    # AUDIT: GOVERNANCE
    # -----------------------------------------------------

    audit(
        db,
        c.id,
        "GOVERNANCE_CHECKED",
        "governance-engine",
        reason,
        str(c.evidence),
        decision,
    )

    # -----------------------------------------------------
    # DECISION-SPECIFIC AUDIT
    # -----------------------------------------------------

    if decision == "HUMAN_REVIEW":

        audit(
            db,
            c.id,
            "APPROVAL_REQUESTED",
            "governance-engine",
            reason,
            str(c.evidence),
            "HUMAN_REVIEW",
        )

    elif decision == "AUTO_APPROVE":

        audit(
            db,
            c.id,
            "RECOVERY_AUTO_APPROVED",
            "governance-engine",
            reason,
            str(c.evidence),
            "AUTO_APPROVED",
        )

    elif decision == "DO_NOT_PURSUE":

        audit(
            db,
            c.id,
            "RECOVERY_NOT_PURSUED",
            "governance-engine",
            reason,
            str(c.evidence),
            "DO_NOT_PURSUE",
        )

    else:

        audit(
            db,
            c.id,
            "RECOVERY_STOPPED",
            "governance-engine",
            reason,
            str(c.evidence),
            "STOPPED",
        )

    db.commit()

    return (
        action,
        decision,
        reason,
    )


# =========================================================
# RECOVERY EXECUTION
# =========================================================

def execute(
    db,
    a,
    actor="system",
):

    # -----------------------------------------------------
    # IDEMPOTENCY
    # -----------------------------------------------------

    if a.status == "EXECUTED":

        existing = (
            db.query(
                SimulatedRecoveryInvoice
            )
            .filter_by(
                leakage_case_id=
                a.leakage_case_id
            )
            .first()
        )

        if existing:

            return (
                a,
                existing.id,
            )

        raise ValueError(
            "Recovery already executed for this case"
        )

    # -----------------------------------------------------
    # APPROVAL GATE
    # -----------------------------------------------------

    if a.status != "APPROVED":

        raise ValueError(
            "Only approved simulated actions can execute"
        )

    # -----------------------------------------------------
    # CASE
    # -----------------------------------------------------

    c = db.get(
        LeakageCase,
        a.leakage_case_id,
    )

    if c is None:

        raise ValueError(
            "Leakage case not found"
        )

    if not c.investigated_at:

        raise ValueError(
            "Investigation is required before recovery"
        )

    # -----------------------------------------------------
    # EXISTING SIMULATED RECOVERY
    # -----------------------------------------------------

    existing = (
        db.query(
            SimulatedRecoveryInvoice
        )
        .filter_by(
            leakage_case_id=c.id
        )
        .first()
    )

    if existing:

        a.status = "EXECUTED"

        a.executed_at = (
            existing.created_at
        )

        c.status = "RECOVERED"

        c.recovered_amount = D(
            existing.amount
        )

        db.commit()

        return (
            a,
            existing.id,
        )

    # -----------------------------------------------------
    # CASE ALREADY RECOVERED
    # -----------------------------------------------------

    if (
        c.status == "RECOVERED"
        or D(c.recovered_amount) > 0
    ):

        raise ValueError(
            "Recovery already executed for this case"
        )

    # -----------------------------------------------------
    # SIMULATED RECOVERY
    # -----------------------------------------------------

    simulated_id = (
        f"SIM-{uuid4().hex[:12].upper()}"
    )

    db.add(
        SimulatedRecoveryInvoice(
            id=simulated_id,
            leakage_case_id=c.id,
            amount=D(
                a.expected_recovery
            ),
        )
    )

    a.status = "EXECUTED"

    a.executed_at = (
        datetime.utcnow()
    )

    a.result = (
        "SIMULATED RECOVERY ONLY: "
        f"adjustment record {simulated_id} "
        "created; no real financial transaction occurred."
    )

    c.status = "RECOVERED"

    c.recovered_amount = D(
        a.expected_recovery
    )

    # -----------------------------------------------------
    # AUDIT
    # -----------------------------------------------------

    audit(
        db,
        c.id,
        "RECOVERY_EXECUTED",
        actor,
        a.result,
        json.dumps(
            {
                "case_id": c.id,
                "amount": str(
                    a.expected_recovery
                ),
                "simulated_invoice_id":
                    simulated_id,
            }
        ),
        "RECOVERED",
    )

    db.commit()

    return (
        a,
        simulated_id,
    )


# =========================================================
# HELPERS
# =========================================================

def cval(db, i):
    return db.get(
        LeakageCase,
        i,
    )


__all__ = [
    "collect_evidence",
    "serialize_evidence",
    "investigate_case",
    "recommend",
    "governance",
    "execute",
]