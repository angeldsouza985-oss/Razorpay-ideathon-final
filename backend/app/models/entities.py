from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase): pass

def money(): return mapped_column(Numeric(18, 2), default=Decimal("0.00"))
class Customer(Base):
    __tablename__="customers"
    id: Mapped[int]=mapped_column(primary_key=True); name: Mapped[str]=mapped_column(String(120)); industry: Mapped[str]=mapped_column(String(80)); customer_segment: Mapped[str]=mapped_column(String(40)); lifetime_value: Mapped[Decimal]=money(); status: Mapped[str]=mapped_column(String(30), default="ACTIVE"); created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)
class Contract(Base):
    __tablename__="contracts"
    id: Mapped[int]=mapped_column(primary_key=True); customer_id: Mapped[int]=mapped_column(ForeignKey("customers.id")); contract_number: Mapped[str]=mapped_column(String(60), unique=True); start_date: Mapped[date]=mapped_column(Date); end_date: Mapped[date]=mapped_column(Date); base_monthly_price: Mapped[Decimal]=money(); discount_percentage: Mapped[Decimal]=mapped_column(Numeric(8,4), default=Decimal("0")); discount_expiry_date: Mapped[date|None]=mapped_column(Date, nullable=True); escalation_percentage: Mapped[Decimal]=mapped_column(Numeric(8,4), default=Decimal("0")); escalation_date: Mapped[date|None]=mapped_column(Date, nullable=True); included_usage: Mapped[Decimal]=mapped_column(Numeric(18,2), default=Decimal("0")); usage_unit: Mapped[str]=mapped_column(String(30), default="units"); overage_price: Mapped[Decimal]=money(); payment_terms_days: Mapped[int]=mapped_column(Integer, default=30); minimum_commitment: Mapped[Decimal]=money(); status: Mapped[str]=mapped_column(String(30), default="ACTIVE"); created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)
class ContractAmendment(Base):
    __tablename__="contract_amendments"
    id: Mapped[int]=mapped_column(primary_key=True); contract_id: Mapped[int]=mapped_column(ForeignKey("contracts.id")); amendment_date: Mapped[date]=mapped_column(Date); description: Mapped[str]=mapped_column(Text); changed_field: Mapped[str]=mapped_column(String(80)); old_value: Mapped[str]=mapped_column(String(100)); new_value: Mapped[str]=mapped_column(String(100)); approved: Mapped[bool]=mapped_column(Boolean, default=False); source: Mapped[str]=mapped_column(String(80))
class UsageRecord(Base):
    __tablename__="usage_records"
    id: Mapped[int]=mapped_column(primary_key=True); contract_id: Mapped[int]=mapped_column(ForeignKey("contracts.id")); customer_id: Mapped[int]=mapped_column(ForeignKey("customers.id")); period_start: Mapped[date]=mapped_column(Date); period_end: Mapped[date]=mapped_column(Date); quantity: Mapped[Decimal]=mapped_column(Numeric(18,2)); unit: Mapped[str]=mapped_column(String(30)); source: Mapped[str]=mapped_column(String(80))
class Invoice(Base):
    __tablename__="invoices"
    id: Mapped[int]=mapped_column(primary_key=True); customer_id: Mapped[int]=mapped_column(ForeignKey("customers.id")); contract_id: Mapped[int]=mapped_column(ForeignKey("contracts.id")); invoice_number: Mapped[str]=mapped_column(String(60), unique=True); invoice_date: Mapped[date]=mapped_column(Date); billing_period_start: Mapped[date]=mapped_column(Date); billing_period_end: Mapped[date]=mapped_column(Date); base_amount: Mapped[Decimal]=money(); usage_amount: Mapped[Decimal]=money(); discount_amount: Mapped[Decimal]=money(); tax_amount: Mapped[Decimal]=money(); total_amount: Mapped[Decimal]=money(); status: Mapped[str]=mapped_column(String(30), default="ISSUED")
class Payment(Base):
    __tablename__="payments"
    id: Mapped[int]=mapped_column(primary_key=True); invoice_id: Mapped[int]=mapped_column(ForeignKey("invoices.id")); customer_id: Mapped[int]=mapped_column(ForeignKey("customers.id")); payment_date: Mapped[date]=mapped_column(Date); amount: Mapped[Decimal]=money(); payment_method: Mapped[str]=mapped_column(String(30)); status: Mapped[str]=mapped_column(String(30), default="SETTLED")
class LeakageCase(Base):
    __tablename__="leakage_cases"
    id: Mapped[int]=mapped_column(primary_key=True); customer_id: Mapped[int]=mapped_column(Integer); contract_id: Mapped[int]=mapped_column(Integer); invoice_id: Mapped[int]=mapped_column(Integer); leakage_type: Mapped[str]=mapped_column(String(60)); expected_amount: Mapped[Decimal]=money(); actual_amount: Mapped[Decimal]=money(); leakage_amount: Mapped[Decimal]=money(); confidence: Mapped[Decimal]=mapped_column(Numeric(5,4)); recoverability: Mapped[Decimal]=mapped_column(Numeric(5,4)); status: Mapped[str]=mapped_column(String(40), default="POTENTIAL LEAKAGE"); recommended_action: Mapped[str]=mapped_column(Text); created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow); classification: Mapped[str|None]=mapped_column(String(40),nullable=True); root_cause: Mapped[str|None]=mapped_column(Text,nullable=True); investigation_summary: Mapped[str|None]=mapped_column(Text,nullable=True); reasoning: Mapped[str|None]=mapped_column(Text,nullable=True); evidence: Mapped[list|None]=mapped_column(JSON,nullable=True); investigated_at: Mapped[datetime|None]=mapped_column(DateTime,nullable=True); recovered_amount: Mapped[Decimal]=money()
class RecoveryAction(Base):
    __tablename__="recovery_actions"
    id: Mapped[int]=mapped_column(primary_key=True); leakage_case_id: Mapped[int]=mapped_column(ForeignKey("leakage_cases.id")); action_type: Mapped[str]=mapped_column(String(60)); expected_recovery: Mapped[Decimal]=money(); intervention_cost: Mapped[Decimal]=money(); approval_required: Mapped[bool]=mapped_column(Boolean, default=True); status: Mapped[str]=mapped_column(String(30), default="RECOMMENDED"); executed_at: Mapped[datetime|None]=mapped_column(DateTime, nullable=True); result: Mapped[str|None]=mapped_column(Text, nullable=True)
class SimulatedRecoveryInvoice(Base):
    __tablename__='simulated_recovery_invoices'
    id: Mapped[str]=mapped_column(String(80),primary_key=True)
    leakage_case_id: Mapped[int]=mapped_column(ForeignKey('leakage_cases.id'),unique=True)
    amount: Mapped[Decimal]=money(); status: Mapped[str]=mapped_column(String(30),default='SIMULATED'); created_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
class AuditEvent(Base):
    __tablename__="audit_events"
    id: Mapped[int]=mapped_column(primary_key=True); leakage_case_id: Mapped[int]=mapped_column(ForeignKey("leakage_cases.id")); timestamp: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow); event_type: Mapped[str]=mapped_column(String(60)); actor: Mapped[str]=mapped_column(String(60)); description: Mapped[str]=mapped_column(Text); evidence: Mapped[str]=mapped_column(Text); result: Mapped[str]=mapped_column(Text)
