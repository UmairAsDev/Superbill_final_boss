from pydantic import BaseModel, Field


from typing import TypedDict, List, Dict, Any

class BillingState(TypedDict):
    note_id : int
    raw_note: str
    encounter_facts: Dict
    billing_response: Dict
    validated_cpt: List[Dict]
    validated_em: List[Dict]
    validated_modifiers: List[Dict]
    superbill: Dict
    
    
class BillingOutput(BaseModel):
    CPT_codes: List[Dict] = Field(default_factory=list)
    E_M_codes: List[Dict] = Field(default_factory=list)
    ICD10_codes: List[str] = Field(default_factory=list)   
    procedure_details: Dict[str, Any] = Field(default_factory=dict)