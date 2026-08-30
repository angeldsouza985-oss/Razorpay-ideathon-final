from pydantic import ValidationError
from ..schemas.investigation import InvestigationResult

ALLOWED_SOURCES={'contract','amendment','invoice','usage','payment','deterministic_engine'}

def validate_provider_result(payload, package):
    result=InvestigationResult.model_validate(payload)
    facts={item['fact'] for item in package['evidence']['evidence_items']}
    if any(claim.source not in ALLOWED_SOURCES or claim.fact not in facts for claim in result.evidence):
        raise ValueError('LLM evidence claim is not grounded in supplied evidence')
    return result.model_dump()
