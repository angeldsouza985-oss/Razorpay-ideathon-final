import json
from decimal import Decimal
from unittest.mock import patch
from app.services.ai_service import AIService

PACKAGE={'case_type':'UNBILLED_USAGE','comparison':{'difference':'54000.00'},'evidence':{'evidence_items':[{'source':'deterministic_engine','fact':'Expected total is ₹94000; actual total is ₹40000; difference is ₹54000.'}]}}

def test_demo_acme():
    with patch.dict('os.environ',{'AI_PROVIDER':'demo'},clear=False):
        service=AIService(); result=service.investigate(PACKAGE)
    assert result['classification']=='CONFIRMED_LEAKAGE'; assert result['confidence']==0.97

def test_valid_llm_response():
    payload={'classification':'CONFIRMED_LEAKAGE','leakage_type':'UNBILLED_USAGE','root_cause':'usage','investigation_summary':'summary','confidence':0.97,'recommended_action':'GENERATE_ADJUSTMENT_INVOICE','evidence':PACKAGE['evidence']['evidence_items'],'reasoning':'grounded'}
    with patch.dict('os.environ',{'AI_PROVIDER':'openai','OPENAI_API_KEY':'test'},clear=False), patch('app.services.ai_service.urlopen') as call:
        call.return_value.__enter__.return_value.read.return_value=json.dumps({'choices':[{'message':{'content':json.dumps(payload)}}]}).encode()
        assert AIService().investigate(PACKAGE)['classification']=='CONFIRMED_LEAKAGE'

def test_malformed_llm_falls_back():
    with patch.dict('os.environ',{'AI_PROVIDER':'openai','OPENAI_API_KEY':'test'},clear=False), patch('app.services.ai_service.urlopen',side_effect=TimeoutError):
        service=AIService(); result=service.investigate(PACKAGE)
    assert result['classification']=='CONFIRMED_LEAKAGE'; assert service.last_meta['fallback_used'] is True

def test_hallucinated_evidence_falls_back():
    payload={'classification':'CONFIRMED_LEAKAGE','leakage_type':'UNBILLED_USAGE','root_cause':'x','investigation_summary':'x','confidence':.97,'recommended_action':'GENERATE_ADJUSTMENT_INVOICE','evidence':[{'source':'invoice','fact':'invented'}],'reasoning':'x'}
    with patch.dict('os.environ',{'AI_PROVIDER':'openai','OPENAI_API_KEY':'test'},clear=False), patch('app.services.ai_service.urlopen') as call:
        call.return_value.__enter__.return_value.read.return_value=json.dumps({'choices':[{'message':{'content':json.dumps(payload)}}]}).encode()
        service=AIService(); assert service.investigate(PACKAGE)['classification']=='CONFIRMED_LEAKAGE'; assert service.last_meta['fallback_used'] is True
