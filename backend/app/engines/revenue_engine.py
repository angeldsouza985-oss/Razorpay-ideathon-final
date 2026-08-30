from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from ..models.entities import Contract, ContractAmendment, Invoice, UsageRecord

CENT = Decimal("0.01")
def D(value: Any) -> Decimal: return Decimal(str(value or 0))
def q(value: Decimal) -> Decimal: return value.quantize(CENT, rounding=ROUND_HALF_UP)

def calculate_expected(contract: Contract, period_start: date, period_end: date, usage: list[UsageRecord], amendments: list[ContractAmendment] | None = None, invoice: Invoice | None = None) -> dict[str, Decimal]:
    base = D(contract.base_monthly_price); discount_pct=D(contract.discount_percentage); escalation_pct=D(contract.escalation_percentage)
    service=Decimal("0")
    for amendment in sorted(amendments or [], key=lambda x:x.amendment_date):
        if amendment.approved and amendment.amendment_date <= period_end:
            if amendment.changed_field == "base_monthly_price": base=D(amendment.new_value)
            elif amendment.changed_field == "discount_percentage": discount_pct=D(amendment.new_value)
            elif amendment.changed_field == "escalation_percentage": escalation_pct=D(amendment.new_value)
            elif amendment.changed_field == "service_charge": service=D(amendment.new_value)
    if contract.escalation_date and period_end >= contract.escalation_date: base *= Decimal("1") + escalation_pct / Decimal("100")
    applicable_discount = discount_pct if contract.discount_expiry_date and period_start <= contract.discount_expiry_date else Decimal("0")
    discount = -(base * applicable_discount / Decimal("100"))
    quantity=sum((D(u.quantity) for u in usage if u.period_start <= period_end and u.period_end >= period_start), Decimal("0"))
    overage=max(Decimal("0"), quantity-D(contract.included_usage)); usage_amount=overage*D(contract.overage_price)
    subtotal=base+discount+usage_amount+service
    tax_rate=(D(invoice.tax_amount)/(D(invoice.base_amount)+D(invoice.usage_amount)+D(invoice.discount_amount))) if invoice and (D(invoice.base_amount)+D(invoice.usage_amount)+D(invoice.discount_amount)) else Decimal("0")
    tax=subtotal*tax_rate; total=subtotal+tax
    return {"expected_base_amount":q(base),"expected_discount":q(discount),"expected_usage_amount":q(usage_amount),"expected_service_charges":q(service),"expected_subtotal":q(subtotal),"expected_tax":q(tax),"expected_total":q(total)}

def compare_invoice(expected: dict[str, Decimal], invoice: Invoice) -> dict[str, Decimal]:
    actual=q(D(invoice.total_amount)); difference=q(expected["expected_total"]-actual)
    return {"expected_amount":expected["expected_total"],"actual_amount":actual,"difference":difference}
