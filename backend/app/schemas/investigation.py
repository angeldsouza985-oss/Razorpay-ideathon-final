from typing import Literal
from pydantic import BaseModel, Field, field_validator

Classification = Literal['CONFIRMED_LEAKAGE','LEGITIMATE_EXCEPTION','INSUFFICIENT_EVIDENCE','DISPUTED']
LeakageType = Literal['MISSED_PRICE_ESCALATION','EXPIRED_DISCOUNT','UNBILLED_USAGE','INCORRECT_QUANTITY','INCORRECT_RATE','MISSING_SERVICE_CHARGE','CONTRACT_AMENDMENT_MISMATCH']
Action = Literal['GENERATE_ADJUSTMENT_INVOICE','CORRECT_FUTURE_BILLING','REQUEST_CONTRACT_VERIFICATION','REQUEST_FINANCE_REVIEW','SEND_CUSTOMER_CLARIFICATION','STOP']
EvidenceSource = Literal['contract','amendment','invoice','usage','payment','deterministic_engine']

class EvidenceClaim(BaseModel):
    source: EvidenceSource
    fact: str = Field(min_length=1)

class InvestigationResult(BaseModel):
    classification: Classification
    leakage_type: LeakageType
    root_cause: str = Field(min_length=1)
    investigation_summary: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    recommended_action: Action
    evidence: list[EvidenceClaim] = Field(min_length=1)
    reasoning: str = Field(min_length=1)
    recoverability: float = Field(default=0, ge=0, le=1)

    @field_validator('evidence')
    @classmethod
    def no_empty_claims(cls, value):
        if any(not item.fact.strip() for item in value):
            raise ValueError('Evidence claims cannot be empty')
        return value
