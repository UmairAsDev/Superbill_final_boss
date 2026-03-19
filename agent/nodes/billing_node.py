import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))
from config.schema import BillingState
from loguru import logger


def superbill_node(state: BillingState) -> BillingState:
    """
    Compile all validated codes into the final superbill structure.
    Uses validated codes from validators, not raw LLM output.
    """
    raw_note = state.get("raw_note", {})
    billing_response = state.get("billing_response", {})
    
    # Get validated codes (these have been checked against the database)
    validated_cpt = state.get("validated_cpt", [])
    validated_em = state.get("validated_em", [])
    validated_icd = state.get("validated_icd", [])
    
    # Procedure details from LLM response
    procedure_details = billing_response.get("procedure_details", {})
    
    # Extract patient and visit info from raw note
    patient_info = raw_note.get("patient", {})
    visit_info = raw_note.get("visit", {})
    
    superbill = {
        "patient_id": patient_info.get("id") or raw_note.get("patient_id"),
        "note_id": state.get("note_id"),
        "note_date": visit_info.get("date") or raw_note.get("note_date"),
        "place_of_service": visit_info.get("place_of_service") or raw_note.get("place_of_service"),
        "billing_codes": {
            "CPT_codes": validated_cpt,
            "E_M_codes": validated_em,
            "ICD10_codes": validated_icd,
            "procedure_details": procedure_details,
        },
        # Keep legacy fields for backwards compatibility
        "diagnoses": raw_note.get("diagnoses"),
        "cpt_codes": validated_cpt,
        "em_codes": validated_em,
    }
    
    # Log superbill summary
    logger.info(f"Superbill compiled for note_id: {state.get('note_id')}")
    logger.info(f"  - CPT codes: {len(validated_cpt)}")
    logger.info(f"  - E/M codes: {len(validated_em)}")
    logger.info(f"  - ICD-10 codes: {len(validated_icd)}")
    
    state["superbill"] = superbill
    return state
