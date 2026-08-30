from datetime import date
from decimal import Decimal
from app.models.entities import Contract,UsageRecord,Invoice,ContractAmendment
from app.engines.revenue_engine import calculate_expected,compare_invoice

def contract(**kw):
    values=dict(id=1,customer_id=1,contract_number="T",start_date=date(2025,1,1),end_date=date(2026,12,31),base_monthly_price=Decimal("50000"),discount_percentage=Decimal("20"),discount_expiry_date=date(2026,1,31),escalation_percentage=Decimal("10"),escalation_date=date(2026,2,1),included_usage=Decimal("100000"),usage_unit="calls",overage_price=Decimal("0.50"))
    values.update(kw)
    return Contract(**values)
def test_price_escalation_and_overage():
 c=contract(); u=[UsageRecord(quantity=Decimal("178000"),period_start=date(2026,2,1),period_end=date(2026,2,28))]; r=calculate_expected(c,date(2026,2,1),date(2026,2,28),u); assert r["expected_base_amount"]==Decimal("55000.00"); assert r["expected_usage_amount"]==Decimal("39000.00"); assert r["expected_total"]==Decimal("94000.00")
def test_expired_discount():
 r=calculate_expected(contract(),date(2026,2,1),date(2026,2,28),[]); assert r["expected_discount"]==Decimal("0.00")
def test_approved_amendment():
 c=contract(); a=ContractAmendment(amendment_date=date(2026,1,1),approved=True,changed_field="base_monthly_price",new_value="40000"); assert calculate_expected(c,date(2026,1,1),date(2026,1,31),[],[a])["expected_base_amount"]==Decimal("40000.00")
def test_invoice_mismatch_and_decimal():
 c=contract(); r=calculate_expected(c,date(2026,1,1),date(2026,1,31),[]); i=Invoice(total_amount=Decimal("30000")); assert compare_invoice(r,i)["difference"]==Decimal("10000.00")
def test_zero_leakage():
 c=contract(discount_percentage=Decimal("0"),discount_expiry_date=None,escalation_percentage=Decimal("0"),escalation_date=None); assert calculate_expected(c,date(2025,1,1),date(2025,1,31),[])["expected_total"]==Decimal("50000.00")
