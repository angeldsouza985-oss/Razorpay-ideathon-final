from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, SessionLocal, engine
from app.models.entities import Customer, Contract, Invoice, LeakageCase
from decimal import Decimal
from datetime import date


def setup_case():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    customer = Customer(name='Endpoint Test Co', industry='SaaS', customer_segment='SMB', lifetime_value=Decimal('100000'))
    db.add(customer); db.flush()
    contract = Contract(customer_id=customer.id, contract_number='END-001', start_date=date(2026,1,1), end_date=date(2026,12,31), base_monthly_price=Decimal('10000'), minimum_commitment=Decimal('10000'))
    db.add(contract); db.flush()
    invoice = Invoice(customer_id=customer.id, contract_id=contract.id, invoice_number='INV-END-001', invoice_date=date(2026,2,1), billing_period_start=date(2026,1,1), billing_period_end=date(2026,1,31), base_amount=Decimal('9000'), total_amount=Decimal('9000'))
    db.add(invoice); db.flush()
    db.add(LeakageCase(customer_id=customer.id, contract_id=contract.id, invoice_id=invoice.id, leakage_type='INCORRECT_RATE', expected_amount=Decimal('10000'), actual_amount=Decimal('9000'), leakage_amount=Decimal('1000'), confidence=Decimal('.90'), recoverability=Decimal('.80'), recommended_action='REVIEW', status='POTENTIAL LEAKAGE'))
    db.commit(); case_id = db.query(LeakageCase).first().id; db.close(); return case_id


def test_list_cases_supports_pagination_and_filters():
    setup_case()
    response = TestClient(app).get('/leakage-cases?limit=1&offset=0&leakage_type=INCORRECT_RATE')
    assert response.status_code == 200
    body = response.json()
    assert body['total'] == 1 and body['limit'] == 1 and len(body['cases']) == 1


def test_case_detail_includes_related_records():
    case_id = setup_case()
    response = TestClient(app).get(f'/leakage-cases/{case_id}')
    assert response.status_code == 200
    body = response.json()
    assert body['case']['id'] == case_id
    assert body['customer']['name'] == 'Endpoint Test Co'
    assert body['contract']['contract_number'] == 'END-001'
    assert body['invoice']['invoice_number'] == 'INV-END-001'
    assert isinstance(body['usage'], list)
    assert body['investigation']['classification'] is None
    assert body['recovery']['actions'] == []


def test_case_detail_missing_returns_404():
    setup_case()
    assert TestClient(app).get('/leakage-cases/9999').status_code == 404
