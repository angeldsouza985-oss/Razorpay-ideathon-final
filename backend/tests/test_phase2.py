from decimal import Decimal
from datetime import date
from app.services.investigation import governance
from app.models.entities import LeakageCase, RecoveryAction

def case(**kw):
    values=dict(classification='CONFIRMED_LEAKAGE',confidence=Decimal('0.97'),evidence=[{'source':'contract','fact':'signed'}])
    values.update(kw); return LeakageCase(**values)

def action(**kw):
    values=dict(expected_recovery=Decimal('54000'),intervention_cost=Decimal('1000'))
    values.update(kw); return RecoveryAction(**values)

def test_high_value_requires_human_review():
    assert governance(case(),action())[:2] == ('HUMAN_REVIEW','Recovery exceeds ₹25,000 approval threshold.')

def test_low_confidence_requires_review():
    assert governance(case(confidence=Decimal('0.79')),action(expected_recovery=Decimal('100')))[:2] == ('HUMAN_REVIEW','Confidence is below 80%.')

def test_legitimate_and_disputed_stop():
    assert governance(case(classification='LEGITIMATE_EXCEPTION'),action(expected_recovery=Decimal('100'))) [0] == 'STOP'
    assert governance(case(classification='DISPUTED'),action(expected_recovery=Decimal('100')))[0] == 'STOP'

def test_missing_evidence_requires_review():
    assert governance(case(evidence=None),action(expected_recovery=Decimal('100')))[0] == 'HUMAN_REVIEW'

def test_cost_rule():
    assert governance(case(),action(expected_recovery=Decimal('100'),intervention_cost=Decimal('100')))[0] == 'DO_NOT_PURSUE'
