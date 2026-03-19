from pydantic import BaseModel, Field
from typing import TypedDict, List, Dict, Any, Optional


class ProcedureDetail(BaseModel):
    """Structured procedure detail model with proper typing."""
    procedure_name: str = ""
    quantity: Optional[int] = None
    anatomic_location: str = ""
    lesion_count: Optional[int] = None
    drug_administered: Optional[str] = None
    drug_strength_mg_per_ml: Optional[float] = None
    drug_total_mg: Optional[float] = None
    drug_total_ml: Optional[float] = None
    method: str = ""
    details: str = ""


class BillingState(TypedDict, total=False):
    """
    State for the billing graph.
    
    Note: encounter_facts was removed as data flows into raw_note.
    All fields used by any node are defined here.
    """
    note_id: int
    raw_note: Dict[str, Any]
    billing_response: Dict[str, Any]
    validated_cpt: List[Dict[str, Any]]
    validated_em: List[Dict[str, Any]]
    validated_icd: List[Dict[str, Any]]
    validated_modifiers: List[Dict[str, Any]]
    # Retrieval node results
    retrieved_cpt: List[Dict[str, Any]]
    retrieved_icd: List[Dict[str, Any]]
    retrieval_context: str
    superbill: Dict[str, Any]
    # Retry / validation tracking
    retry_count: int
    validation_errors: List[Dict[str, Any]]
    all_em_rejected: bool
    all_icd_rejected: bool
    final_output: List[Dict[str, Any]]
    # Error tracking
    error: Optional[str]
    error_details: Optional[Dict[str, Any]]


class BillingOutput(BaseModel):
    """Output model for billing results with properly typed fields."""
    CPT_codes: List[Dict[str, Any]] = Field(default_factory=list)
    E_M_codes: List[Dict[str, Any]] = Field(default_factory=list)
    ICD10_codes: List[Dict[str, Any]] = Field(default_factory=list)
    procedure_details: ProcedureDetail = Field(default_factory=ProcedureDetail)


class ProcedureListOutput(BaseModel):
    """Output model for multiple procedures."""
    procedures: List[ProcedureDetail] = Field(default_factory=list)
