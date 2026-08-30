from datetime import date
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.entities import Base, Customer, Contract, Invoice, UsageRecord
from app.engines.revenue_engine import calculate_expected, compare_invoice
from scripts.seed_data import seed_database

def test_seeded_acme_hero_numbers():
    engine=create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    db=sessionmaker(bind=engine)()
    seed_database(db)
    acme=db.query(Customer).filter_by(name='Acme Technologies').one()
    contract=db.query(Contract).filter_by(customer_id=acme.id).one()
    invoice=db.query(Invoice).filter_by(contract_id=contract.id,billing_period_start=date(2026,2,1)).one()
    usage=db.query(UsageRecord).filter_by(contract_id=contract.id,period_start=date(2026,2,1)).all()
    expected=calculate_expected(contract,invoice.billing_period_start,invoice.billing_period_end,usage,[],invoice)
    comparison=compare_invoice(expected,invoice)
    assert expected['expected_total']==Decimal('94000.00')
    assert comparison['actual_amount']==Decimal('40000.00')
    assert comparison['difference']==Decimal('54000.00')
    assert sum((u.quantity for u in usage),Decimal(0))==Decimal('178000')
    db.close()
    engine.dispose()
