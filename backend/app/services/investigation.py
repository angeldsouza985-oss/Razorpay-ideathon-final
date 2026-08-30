from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import uuid4
import json
from typing import Any
from sqlalchemy.orm import Session
from ..models.entities import *
from ..engines.revenue_engine import calculate_expected, compare_invoice, D
from .ai_service import AIService

CLASSIFICATIONS = {'CONFIRMED_LEAKAGE','LEGITIMATE_EXCEPTION','INSUFFICIENT_EVIDENCE','DISPUTED'}
RECOVERY_ACTIONS = {'GENERATE_ADJUSTMENT_INVOICE','CORRECT_FUTURE_BILLING','REQUEST_CONTRACT_VERIFICATION','REQUEST_FINANCE_REVIEW','SEND_CUSTOMER_CLARIFICATION','STOP'}

@dataclass
class Evidence:
    customer: Customer
    contract: Contract
    amendments: list
    invoice: Invoice
    usage: list
    payments: list
    expected: dict
    comparison: dict

def audit(db, case_id, event, actor, description, evidence='', result=''):
    db.add(AuditEvent(leakage_case_id=case_id,event_type=event,actor=actor,description=description,evidence=evidence,result=result))

def collect_evidence(db: Session, case_id: int) -> Evidence:
    case=db.get(LeakageCase,case_id)
    if not case: raise ValueError('Leakage case not found')
    customer=db.get(Customer,case.customer_id); contract=db.get(Contract,case.contract_id); invoice=db.get(Invoice,case.invoice_id)
    if not customer or not contract or not invoice: raise ValueError('Case references missing financial records')
    amendments=db.query(ContractAmendment).filter_by(contract_id=contract.id).order_by(ContractAmendment.amendment_date).all()
    usage=db.query(UsageRecord).filter(UsageRecord.contract_id==contract.id,UsageRecord.period_start<=invoice.billing_period_end,UsageRecord.period_end>=invoice.billing_period_start).all()
    payments=db.query(Payment).filter_by(invoice_id=invoice.id).all()
    expected=calculate_expected(contract,invoice.billing_period_start,invoice.billing_period_end,usage,amendments,invoice)
    comparison=compare_invoice(expected,invoice)
    return Evidence(customer,contract,amendments,invoice,usage,payments,expected,comparison)

def evidence_items(e: Evidence):
    items=[
      {'source':'contract','fact':f'Base monthly price is ₹{e.contract.base_monthly_price}; included usage is {e.contract.included_usage} {e.contract.usage_unit}; overage is ₹{e.contract.overage_price}/{e.contract.usage_unit}.'},
      {'source':'usage','fact':f'{sum((D(u.quantity) for u in e.usage),Decimal(0))} {e.contract.usage_unit} recorded in the invoice period.'},
      {'source':'invoice','fact':f'Invoice total is ₹{e.invoice.total_amount}.'},
      {'source':'deterministic_engine','fact':f'Expected total is ₹{e.expected["expected_total"]}; actual total is ₹{e.comparison["actual_amount"]}; difference is ₹{e.comparison["difference"]}.'},
    ]
    for a in e.amendments:
        if a.approved: items.append({'source':'amendment','fact':f'Approved amendment dated {a.amendment_date}: {a.changed_field} changed from {a.old_value} to {a.new_value}.'})
    for p in e.payments: items.append({'source':'payment','fact':f'Payment of ₹{p.amount} has status {p.status}.'})
    return items

def serialize_evidence(e):
    return {'customer':{'id':e.customer.id,'name':e.customer.name},'contract':{'id':e.contract.id,'contract_number':e.contract.contract_number},'amendments':[{'id':a.id,'description':a.description,'approved':a.approved,'changed_field':a.changed_field,'old_value':a.old_value,'new_value':a.new_value} for a in e.amendments],'invoice':{'id':e.invoice.id,'total_amount':str(e.invoice.total_amount)},'usage':[{'quantity':str(u.quantity),'unit':u.unit} for u in e.usage],'payments':[{'amount':str(p.amount),'status':p.status} for p in e.payments],'expected_invoice':{k:str(v) for k,v in e.expected.items()},'difference':str(e.comparison['difference']),'evidence_items':evidence_items(e)}

def _deterministic_result(e, case):
    diff=e.comparison['difference']; approved=[a for a in e.amendments if a.approved and a.amendment_date<=e.invoice.billing_period_end]
    relevant=[a for a in approved if a.changed_field in {'base_monthly_price','discount_percentage','escalation_percentage','service_charge'}]
    # Engine has already applied approved amendments. A non-positive difference is not leakage.
    if diff<=0: classification='LEGITIMATE_EXCEPTION' if relevant else 'INSUFFICIENT_EVIDENCE'
    else: classification='CONFIRMED_LEAKAGE'
    confidence=Decimal('0.97') if diff>0 and not relevant else Decimal('0.95') if diff<=0 and relevant else Decimal('0.60')
    roots={'UNBILLED_USAGE':'Usage exceeded the contracted allowance and the invoice omitted the deterministic overage charge.','MISSED_PRICE_ESCALATION':'The invoice used the pre-escalation base price after the contractual effective date.','EXPIRED_DISCOUNT':'The invoice continued applying a discount after its expiry date.','CONTRACT_AMENDMENT_MISMATCH':'The commercial terms differ from an approved amendment.'}
    return {'classification':classification,'root_cause':roots.get(case.leakage_type,'Invoice is below the deterministic contract calculation.'),'summary':f'Deterministic comparison found ₹{diff} difference; AI interpretation is constrained to supplied evidence.','confidence':confidence,'recoverability':Decimal('0.90') if classification=='CONFIRMED_LEAKAGE' else Decimal('0'),'recommended_action':'GENERATE_ADJUSTMENT_INVOICE' if classification=='CONFIRMED_LEAKAGE' else 'STOP'}

def investigate_case(db: Session, case_id:int):
    case=db.get(LeakageCase,case_id)
    if not case: raise ValueError('Leakage case not found')
    if case.classification and case.investigated_at: return case
    e=collect_evidence(db,case_id); items=evidence_items(e); audit(db,case_id,'EVIDENCE_COLLECTED','evidence-collector','Evidence package collected.',str(items),'READY'); audit(db,case_id,'INVESTIGATION_STARTED','investigation-agent','Investigation started.',str(items),'IN_PROGRESS')
    ai=AIService(); package={'case_type':case.leakage_type,'evidence':{'customer':{'id':e.customer.id,'name':e.customer.name},'contract':{'id':e.contract.id,'contract_number':e.contract.contract_number},'amendments':[{'id':a.id,'approved':a.approved,'changed_field':a.changed_field,'old_value':a.old_value,'new_value':a.new_value} for a in e.amendments],'invoice':{'id':e.invoice.id,'total_amount':str(e.invoice.total_amount)},'usage':[{'quantity':str(u.quantity),'unit':u.unit} for u in e.usage],'payments':[{'amount':str(p.amount),'status':p.status} for p in e.payments],'expected_invoice':{k:str(v) for k,v in e.expected.items()},'difference':str(e.comparison['difference']),'evidence_items':items},'expected_invoice':{k:str(v) for k,v in e.expected.items()},'comparison':{k:str(v) for k,v in e.comparison.items()}}
    audit(db,case_id,'AI_INVESTIGATION_STARTED',ai.provider,'AI investigation started.',json.dumps(ai.last_meta),'STARTED')
    result=ai.investigate(package)
    audit(db,case_id,'AI_INVESTIGATION_COMPLETED',ai.provider,'AI investigation completed.',json.dumps(ai.last_meta),result.get('classification','INVALID'))
    if result.get('classification') not in CLASSIFICATIONS: result=_deterministic_result(e,case)
    if result.get('recommended_action') not in RECOVERY_ACTIONS: result['recommended_action']='STOP'
    case.classification=result['classification']; case.root_cause=result.get('root_cause',''); case.investigation_summary=result.get('investigation_summary',result.get('summary','')); case.reasoning=result.get('reasoning',''); case.evidence=[{'source':x['source'],'fact':x['fact']} for x in result.get('evidence',items)]; case.investigated_at=datetime.utcnow(); case.confidence=D(result.get('confidence',0)); case.recoverability=D(result.get('recoverability',0)); case.recommended_action=result['recommended_action']; case.status={'CONFIRMED_LEAKAGE':'CONFIRMED','LEGITIMATE_EXCEPTION':'LEGITIMATE'}.get(case.classification,'STOPPED')
    audit(db,case_id,'INVESTIGATION_COMPLETED','investigation-agent',case.investigation_summary,str(items),case.classification)
    audit(db,case_id,'LEAKAGE_CONFIRMED' if case.classification=='CONFIRMED_LEAKAGE' else 'LEAKAGE_REJECTED','investigation-agent',case.root_cause,str(items),case.classification)
    db.commit(); return case

def governance(c, action, amendments=None):
    amount=D(action.expected_recovery); confidence=D(c.confidence)
    if any(getattr(a,'approved',False) and getattr(a,'changed_field','') in {'base_monthly_price','discount_percentage','escalation_percentage','service_charge','overage_price','included_usage'} for a in (amendments or [])):
        return 'STOP','Conflicting approved amendment requires commercial review.',True
    if c.classification=='DISPUTED': return 'STOP','Disputed cases cannot be recovered.',True
    if c.classification!='CONFIRMED_LEAKAGE': return 'STOP','Only confirmed leakage can be recovered.',True
    if not c.evidence: return 'HUMAN_REVIEW','Evidence is missing.',True
    if confidence<Decimal('.80'): return 'HUMAN_REVIEW','Confidence is below 80%.',True
    if amount>=Decimal('25000'): return 'HUMAN_REVIEW','Recovery exceeds ₹25,000 approval threshold.',True
    if amount<=D(action.intervention_cost): return 'DO_NOT_PURSUE','Expected recovery does not exceed intervention cost.',False
    return 'AUTO_APPROVE','Evidence and economics satisfy recovery policy.',False

def recommend(db, case_id):
    c=db.get(LeakageCase,case_id)
    if not c: raise ValueError('Leakage case not found')
    if not c.classification: c=investigate_case(db,case_id)
    existing=db.query(RecoveryAction).filter_by(leakage_case_id=c.id).order_by(RecoveryAction.id.desc()).first()
    if existing: return existing, ('HUMAN_REVIEW' if existing.status=='PENDING_APPROVAL' else 'STOP' if existing.status in {'STOPPED','REJECTED'} else 'AUTO_APPROVE'), existing.result or 'Existing idempotent recovery action.'
    action=RecoveryAction(leakage_case_id=c.id,action_type=c.recommended_action,expected_recovery=D(c.leakage_amount) if c.classification=='CONFIRMED_LEAKAGE' else Decimal(0),intervention_cost=Decimal('1000'),status='RECOMMENDED')
    db.add(action); db.flush(); evidence=collect_evidence(db,c.id); decision,reason,approval=governance(c,action,evidence.amendments); action.approval_required=approval; action.result=reason; action.status='PENDING_APPROVAL' if decision=='HUMAN_REVIEW' else 'APPROVED' if decision=='AUTO_APPROVE' else 'STOPPED'; c.status='RECOVERY_PENDING' if decision=='HUMAN_REVIEW' else c.status
    audit(db,c.id,'RECOVERY_RECOMMENDED','recovery-strategy',f'Recommended {action.action_type}.',str(c.evidence),decision); audit(db,c.id,'GOVERNANCE_CHECKED','governance-engine',reason,str(c.evidence),decision); audit(db,c.id,'APPROVAL_REQUESTED' if decision=='HUMAN_REVIEW' else 'STOPPED','governance-engine',reason,str(c.evidence),decision); db.commit(); return action,decision,reason

def execute(db,a,actor='system'):
    if a.status!='APPROVED': raise ValueError('Only approved simulated actions can execute')
    c=db.get(LeakageCase,a.leakage_case_id)
    if c is None or not c.investigated_at: raise ValueError('Investigation is required before recovery')
    if c.status=='RECOVERED' or a.status=='EXECUTED' or D(c.recovered_amount)>0: raise ValueError('Recovery already executed for this case')
    simulated_id=f'SIM-{uuid4().hex[:12].upper()}'
    db.add(SimulatedRecoveryInvoice(id=simulated_id,leakage_case_id=c.id,amount=D(a.expected_recovery)))
    a.status='EXECUTED'; a.executed_at=datetime.utcnow(); a.result=f'SIMULATED RECOVERY ONLY: adjustment record {simulated_id} created; no real financial transaction occurred.'; c.status='RECOVERED'; c.recovered_amount=D(a.expected_recovery); audit(db,c.id,'RECOVERY_EXECUTED',actor,a.result,json.dumps({'case_id':c.id,'amount':str(a.expected_recovery),'simulated_invoice_id':simulated_id}),'RECOVERED'); db.commit(); return a,simulated_id

def cval(db,i): return db.get(LeakageCase,i)
__all__=['collect_evidence','serialize_evidence','investigate_case','recommend','governance','execute']
