import random
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.entities import *
NAMES=["Acme Technologies","NovaCloud","FinEdge Systems","Vertex Labs","Orbit Analytics","BluePeak Digital","ScaleGrid","CloudForge"]
def seed_database(db:Session):
    for table in [AuditEvent,RecoveryAction,LeakageCase,Payment,Invoice,UsageRecord,ContractAmendment,Contract,Customer]: db.query(table).delete()
    random.seed(42); customers=[]; contracts=[]
    for i in range(100):
        c=Customer(name=NAMES[0] if i==0 else f"{random.choice(NAMES[1:])} India {i:03d}",industry=random.choice(["SaaS","Fintech","E-commerce","Logistics"]),customer_segment=random.choice(["SMB","Mid-market","Enterprise"]),lifetime_value=Decimal(random.randint(200000,5000000)),status="ACTIVE"); db.add(c); db.flush(); customers.append(c)
        contract=Contract(customer_id=c.id,contract_number=f"BG-{i+1:04d}",start_date=date(2025,1,1),end_date=date(2026,12,31),base_monthly_price=Decimal("50000") if i==0 else Decimal(random.choice(["25000","50000","75000","120000"])),discount_percentage=Decimal("20") if i==0 else Decimal(random.choice(["0","10","15"])),discount_expiry_date=date(2026,1,31) if i==0 else date(2025,12,31),escalation_percentage=Decimal("10") if i==0 else Decimal("5"),escalation_date=date(2026,2,1),included_usage=Decimal("100000") if i==0 else Decimal("50000"),usage_unit="API calls",overage_price=Decimal("0.50") if i==0 else Decimal("1.00"),payment_terms_days=30,minimum_commitment=Decimal("0")); db.add(contract); db.flush(); contracts.append(contract)
        if i==1: db.add(ContractAmendment(contract_id=contract.id,amendment_date=date(2025,7,1),description="Approved rate reduction",changed_field="base_monthly_price",old_value=str(contract.base_monthly_price),new_value="20000",approved=True,source="signed amendment"))
    for i,c in enumerate(contracts):
        for month in range(12):
            start=date(2026, month + 1, 1); end=(start+timedelta(days=32)).replace(day=1)-timedelta(days=1)
            # The February Acme fixture is intentionally exact: 178,000 calls and a ₹40,000 invoice.
            qty=Decimal("178000") if i==0 and month==1 else Decimal(random.randint(30000,120000)); db.add(UsageRecord(contract_id=c.id,customer_id=c.customer_id,period_start=start,period_end=end,quantity=qty,unit="API calls",source="metered API"));
            for _ in range(99): db.add(UsageRecord(contract_id=c.id,customer_id=c.customer_id,period_start=start,period_end=end,quantity=Decimal("0"),unit="API calls",source="metered API batch"))
            base=Decimal("40000") if i==0 and month==1 else c.base_monthly_price; usage=Decimal("0") if i==0 and month==1 else max(Decimal(0),qty-c.included_usage)*c.overage_price; discount=Decimal("0") if (i==0 and month==1) else -(base*c.discount_percentage/Decimal(100) if start<=c.discount_expiry_date else Decimal(0)); total=base+usage+discount; inv=Invoice(customer_id=c.customer_id,contract_id=c.id,invoice_number=f"INV-{i+1:03d}-{month+1:02d}",invoice_date=end+timedelta(days=1),billing_period_start=start,billing_period_end=end,base_amount=base,usage_amount=usage,discount_amount=discount,tax_amount=Decimal(0),total_amount=total); db.add(inv); db.flush(); db.add(Payment(invoice_id=inv.id,customer_id=c.customer_id,payment_date=end+timedelta(days=15),amount=total,payment_method="NEFT",status="SETTLED"))
    db.commit()
if __name__=="__main__":
    from app.database import SessionLocal,init_db
    init_db(); seed_database(SessionLocal())
