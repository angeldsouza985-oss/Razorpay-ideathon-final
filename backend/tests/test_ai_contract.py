import json
from unittest.mock import patch
from app.services.ai_service import AIService

PACKAGE={'case_type':'UNBILLED_USAGE','comparison':{'difference':'54000.00'},'evidence':{'evidence_items':[{'source':'deterministic_engine','fact':'Expected total is ₹94000; actual total is ₹40000; difference is ₹54000.'}]}}


def test_demo_is_truthful_fallback():
    with patch.dict('os.environ', {'AI_PROVIDER':'demo'}, clear=False):
        service=AIService(); result=service.investigate(PACKAGE)
    assert result['classification']=='CONFIRMED_LEAKAGE'
    assert service.last_meta == {'provider':'demo','model':'deterministic','fallback_used':True,'fallback_reason':'missing API key or provider disabled'}


def test_invalid_llm_output_falls_back_and_never_changes_finance():
    payload={'classification':'NOT_ALLOWED','leakage_type':'UNBILLED_USAGE','root_cause':'x','investigation_summary':'x','confidence':.97,'recommended_action':'GENERATE_ADJUSTMENT_INVOICE','evidence':PACKAGE['evidence']['evidence_items'],'reasoning':'x'}
    with patch.dict('os.environ', {'AI_PROVIDER':'openai','OPENAI_API_KEY':'test'}, clear=False), patch('app.services.ai_service.urlopen') as call:
        call.return_value.__enter__.return_value.read.return_value=json.dumps({'choices':[{'message':{'content':json.dumps(payload)}}]}).encode()
        service=AIService(); result=service.investigate(PACKAGE)
    assert result['classification']=='CONFIRMED_LEAKAGE'
    assert service.last_meta['provider']=='demo' and service.last_meta['fallback_used'] is True
    assert PACKAGE['comparison']['difference']=='54000.00'
