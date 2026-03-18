from pydantic import BaseModel, Field


from typing import TypedDict, List, Dict, Any

class BillingState(TypedDict):
    note_id : int
    raw_note: Dict[str, Any]
    encounter_facts: Dict[str, Any]
    billing_response: Dict[str, Any]
    validated_cpt: List[Dict[str, Any]]
    validated_em: List[Dict[str, Any]]
    validated_modifiers: List[Dict[str, Any]]
    superbill: Dict[str, Any]
    # final_output: List[Dict[str, Any]]
    
    
class BillingOutput(BaseModel):
    CPT_codes: List[Dict[str, Any]] = Field(default_factory=list)
    E_M_codes: List[Dict[str, Any]] = Field(default_factory=list)
    ICD10_codes: List[Dict[str, Any]] = Field(default_factory=list)
    procedure_details: Dict[str, Any] = Field(default_factory=dict)