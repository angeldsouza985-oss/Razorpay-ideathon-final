import random
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.entities import (
    AuditEvent,
    Contract,
    ContractAmendment,
    Customer,
    Invoice,
    LeakageCase,
    Payment,
    RecoveryAction,
    SimulatedRecoveryInvoice,
    UsageRecord,
)


NAMES = [
    "Acme Technologies",
    "NovaCloud",
    "FinEdge Systems",
    "Vertex Labs",
    "Orbit Analytics",
    "BluePeak Digital",
    "ScaleGrid",
    "CloudForge",
]


def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"))


def seed_database(db: Session):

    # =========================================================
    # CLEAR OLD DATA
    # =========================================================

    tables = [
        AuditEvent,
        SimulatedRecoveryInvoice,
        RecoveryAction,
        LeakageCase,
        Payment,
        Invoice,
        UsageRecord,
        ContractAmendment,
        Contract,
        Customer,
    ]

    for table in tables:
        db.query(table).delete()

    db.commit()

    random.seed(42)

    customers = []
    contracts = []

    # =========================================================
    # CUSTOMERS + CONTRACTS
    # =========================================================

    for i in range(100):

        customer = Customer(
            name=(
                NAMES[0]
                if i == 0
                else f"{random.choice(NAMES[1:])} India {i:03d}"
            ),
            industry=random.choice(
                [
                    "SaaS",
                    "Fintech",
                    "E-commerce",
                    "Logistics",
                ]
            ),
            customer_segment=random.choice(
                [
                    "SMB",
                    "Mid-market",
                    "Enterprise",
                ]
            ),
            lifetime_value=Decimal(
                random.randint(200000, 5000000)
            ),
            status="ACTIVE",
        )

        db.add(customer)
        db.flush()

        customers.append(customer)

        # -----------------------------------------------------
        # Contract
        # -----------------------------------------------------

        if i == 0:

            base_price = Decimal("50000")
            discount = Decimal("20")
            discount_expiry = date(2026, 1, 31)
            escalation = Decimal("10")
            included_usage = Decimal("100000")
            overage = Decimal("0.50")

        else:

            base_price = Decimal(
                random.choice(
                    [
                        "25000",
                        "50000",
                        "75000",
                        "120000",
                    ]
                )
            )

            discount = Decimal(
                random.choice(
                    [
                        "0",
                        "10",
                        "15",
                    ]
                )
            )

            discount_expiry = date(2025, 12, 31)

            escalation = Decimal("5")

            included_usage = Decimal("50000")

            overage = Decimal("1.00")

        contract = Contract(
            customer_id=customer.id,
            contract_number=f"BG-{i + 1:04d}",
            start_date=date(2025, 1, 1),
            end_date=date(2026, 12, 31),
            base_monthly_price=base_price,
            discount_percentage=discount,
            discount_expiry_date=discount_expiry,
            escalation_percentage=escalation,
            escalation_date=date(2026, 2, 1),
            included_usage=included_usage,
            usage_unit="API calls",
            overage_price=overage,
            payment_terms_days=30,
            minimum_commitment=Decimal("0"),
            status="ACTIVE",
        )

        db.add(contract)
        db.flush()

        contracts.append(contract)

        # -----------------------------------------------------
        # Approved amendment for customer #2
        # -----------------------------------------------------

        if i == 1:

            db.add(
                ContractAmendment(
                    contract_id=contract.id,
                    amendment_date=date(2025, 7, 1),
                    description="Approved rate reduction",
                    changed_field="base_monthly_price",
                    old_value=str(base_price),
                    new_value="20000",
                    approved=True,
                    source="signed amendment",
                )
            )

    db.flush()

    # =========================================================
    # INVOICE GENERATION
    # =========================================================

    invoice_counter = 0

    # Intentional leakage fixtures.
    #
    # Key:
    # (customer_index, month_index): leakage amount
    #
    # month_index:
    # 0 = January
    # 1 = February
    # etc.
    #
    # Case #1:
    # Acme February has 178k usage but invoice does not
    # include the usage charge.
    #
    # Case #2:
    # Customer #2 February has a ₹5,000 base-price mismatch.
    # =========================================================

    anomalies = {
        # Major demo case
        (0, 1): "ACME_UNBILLED_USAGE",

        # Second major demo case
        (1, 1): "MISSED_ESCALATION",

        # Additional realistic smaller cases
        (5, 2): "SMALL_UNDERBILL",
        (12, 3): "SMALL_UNDERBILL",
        (18, 4): "SMALL_UNDERBILL",
        (27, 5): "SMALL_UNDERBILL",
        (34, 6): "SMALL_UNDERBILL",
        (43, 7): "SMALL_UNDERBILL",
        (51, 8): "SMALL_UNDERBILL",
        (62, 9): "SMALL_UNDERBILL",
        (74, 10): "SMALL_UNDERBILL",
        (88, 11): "SMALL_UNDERBILL",
    }

    for i, contract in enumerate(contracts):

        for month in range(12):

            start = date(
                2026,
                month + 1,
                1,
            )

            end = (
                start + timedelta(days=32)
            ).replace(day=1) - timedelta(days=1)

            anomaly = anomalies.get((i, month))

            # =================================================
            # USAGE
            # =================================================

            if anomaly == "ACME_UNBILLED_USAGE":

                quantity = Decimal("178000")

            else:

                quantity = Decimal(
                    random.randint(
                        30000,
                        120000,
                    )
                )

            # Primary usage record
            db.add(
                UsageRecord(
                    contract_id=contract.id,
                    customer_id=contract.customer_id,
                    period_start=start,
                    period_end=end,
                    quantity=quantity,
                    unit="API calls",
                    source="metered API",
                )
            )

            # Additional zero-value metering records.
            # These simulate batched meter events without
            # changing the actual quantity.
            for _ in range(9):

                db.add(
                    UsageRecord(
                        contract_id=contract.id,
                        customer_id=contract.customer_id,
                        period_start=start,
                        period_end=end,
                        quantity=Decimal("0"),
                        unit="API calls",
                        source="metered API batch",
                    )
                )

            # =================================================
            # CALCULATE CORRECT CONTRACT VALUE
            # =================================================

            base = contract.base_monthly_price

            # Apply approved amendment
            if i == 1 and start >= date(2026, 2, 1):
                base = Decimal("20000")

            # Apply escalation
            if (
                contract.escalation_date
                and end >= contract.escalation_date
            ):

                base = base * (
                    Decimal("1")
                    + contract.escalation_percentage
                    / Decimal("100")
                )

            # Discount
            if (
                contract.discount_expiry_date
                and start <= contract.discount_expiry_date
            ):

                discount = -(
                    base
                    * contract.discount_percentage
                    / Decimal("100")
                )

            else:

                discount = Decimal("0")

            # Usage overage
            overage = max(
                Decimal("0"),
                quantity - contract.included_usage,
            )

            usage_amount = (
                overage * contract.overage_price
            )

            correct_total = (
                base
                + discount
                + usage_amount
            )

            # =================================================
            # CREATE INTENTIONAL ANOMALIES
            # =================================================

            invoice_base = base
            invoice_usage = usage_amount
            invoice_discount = discount
            invoice_total = correct_total

            # -------------------------------------------------
            # CASE #1 — ACME UNBILLED USAGE
            # -------------------------------------------------

            if anomaly == "ACME_UNBILLED_USAGE":

                # Correct expected:
                #
                # Base after escalation = ₹55,000
                # Usage = 78,000 × ₹0.50 = ₹39,000
                # Expected = ₹94,000
                #
                # Invoice contains only ₹40,000.
                #
                # Leakage = ₹54,000

                invoice_base = Decimal("40000")
                invoice_usage = Decimal("0")
                invoice_discount = Decimal("0")
                invoice_total = Decimal("40000")

            # -------------------------------------------------
            # CASE #2 — MISSED PRICE ESCALATION
            # -------------------------------------------------

            elif anomaly == "MISSED_ESCALATION":

                # Expected base:
                #
                # Amendment changes ₹50,000 → ₹20,000
                # Escalation = 5%
                # Expected = ₹21,000
                #
                # We intentionally invoice ₹16,000.
                #
                # Leakage = ₹5,000

                invoice_base = Decimal("16000")
                invoice_usage = Decimal("0")
                invoice_discount = Decimal("0")
                invoice_total = Decimal("16000")

            # -------------------------------------------------
            # SMALL REALISTIC UNDERBILLING
            # -------------------------------------------------

            elif anomaly == "SMALL_UNDERBILL":

                invoice_total = max(
                    Decimal("0"),
                    correct_total - Decimal("2500"),
                )

                # Keep the invoice components simple.
                invoice_base = invoice_total
                invoice_usage = Decimal("0")
                invoice_discount = Decimal("0")

            # =================================================
            # INVOICE
            # =================================================

            invoice_counter += 1

            invoice = Invoice(
                customer_id=contract.customer_id,
                contract_id=contract.id,
                invoice_number=(
                    f"INV-{i + 1:03d}-{month + 1:02d}"
                ),
                invoice_date=end + timedelta(days=1),
                billing_period_start=start,
                billing_period_end=end,
                base_amount=money(invoice_base),
                usage_amount=money(invoice_usage),
                discount_amount=money(invoice_discount),
                tax_amount=Decimal("0"),
                total_amount=money(invoice_total),
                status="ISSUED",
            )

            db.add(invoice)
            db.flush()

            # =================================================
            # PAYMENT
            # =================================================

            db.add(
                Payment(
                    invoice_id=invoice.id,
                    customer_id=contract.customer_id,
                    payment_date=end + timedelta(days=15),
                    amount=money(invoice_total),
                    payment_method="NEFT",
                    status="SETTLED",
                )
            )

    db.commit()

    return {
        "status": "seeded",
        "customers": db.query(Customer).count(),
        "invoices": db.query(Invoice).count(),
        "usage_records": db.query(UsageRecord).count(),
    }


# =============================================================
# DIRECT EXECUTION
# =============================================================

if __name__ == "__main__":

    from app.database import SessionLocal, init_db

    init_db()

    db = SessionLocal()

    try:
        result = seed_database(db)
        print(result)
    finally:
        db.close()