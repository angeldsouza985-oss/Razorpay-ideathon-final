from decimal import Decimal
from app.services.investigation import governance
from app.models.entities import LeakageCase, RecoveryAction

def test_low_value_auto_approves():
    c=LeakageCase(classification='CONFIRMED_LEAKAGE', confidence=Decimal('.90'), evidence=[{'source':'x'}])
    a=RecoveryAction(expected_recovery=Decimal('100'), intervention_cost=Decimal('1'))
    assert governance(c,a)[0]=='AUTO_APPROVE'

def test_conflicting_amendment_stops():
    c=LeakageCase(classification='CONFIRMED_LEAKAGE', confidence=Decimal('.95'), evidence=[{'source':'x'}])
    a=RecoveryAction(expected_recovery=Decimal('100'), intervention_cost=Decimal('1'))
    class Amendment: approved=True; changed_field='base_monthly_price'
    assert governance(c,a,[Amendment()])[0]=='STOP'
