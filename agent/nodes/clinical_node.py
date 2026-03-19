import sys
import pathlib
from typing import Dict, Any

sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))

from context.note_context import structured_notes_context
from config.schema import BillingState
from loguru import logger


async def clinical_node(state: BillingState) -> BillingState:
    """
    Clinical node that extracts and structures clinical data from notes.
    
    Args:
        state: The current billing state containing note_id
        
    Returns:
        Updated state with raw_note populated or error set
    """
    # Input validation: check note_id is present and valid
    note_id = state.get("note_id")
    
    if note_id is None:
        error_msg = "note_id is missing from state"
        logger.error(error_msg)
        state["error"] = error_msg
        state["error_details"] = {"field": "note_id", "reason": "missing"}
        return state
    
    # Validate note_id is a positive integer
    if not isinstance(note_id, int):
        try:
            note_id = int(note_id)
        except (ValueError, TypeError) as e:
            error_msg = f"note_id must be a valid integer, got: {type(note_id).__name__}"
            logger.error(f"{error_msg} - {e}")
            state["error"] = error_msg
            state["error_details"] = {"field": "note_id", "reason": "invalid_type", "value": str(note_id)}
            return state
    
    if note_id <= 0:
        error_msg = f"note_id must be a positive integer, got: {note_id}"
        logger.error(error_msg)
        state["error"] = error_msg
        state["error_details"] = {"field": "note_id", "reason": "invalid_value", "value": note_id}
        return state
    
    logger.info(f"Processing clinical data for note_id: {note_id}")
    
    try:
        # Fetch structured notes context
        encounter_facts = await structured_notes_context(note_id)
        
        # Check if we got valid data back
        if not encounter_facts:
            error_msg = f"No clinical data found for note_id: {note_id}"
            logger.warning(error_msg)
            state["error"] = error_msg
            state["error_details"] = {"field": "raw_note", "reason": "empty_response", "note_id": note_id}
            state["raw_note"] = {}
            return state
        
        # Check for required clinical fields
        clinical_data = encounter_facts.get("clinical", {})
        procedures_data = encounter_facts.get("procedures", [])
        
        # Log what was extracted
        logger.info(f"Extracted data for note_id {note_id}:")
        logger.info(f"  - Patient ID: {encounter_facts.get('patient', {}).get('id')}")
        logger.info(f"  - Visit date: {encounter_facts.get('visit', {}).get('date')}")
        logger.info(f"  - Complaints present: {bool(clinical_data.get('complaints'))}")
        logger.info(f"  - Assessment present: {bool(clinical_data.get('assessment'))}")
        logger.info(f"  - Procedures count: {len(procedures_data)}")
        logger.info(f"  - Diagnoses count: {len(encounter_facts.get('diagnoses', []))}")
        logger.info(f"  - Medications count: {len(encounter_facts.get('medications', []))}")
        
        # Log procedure details if present
        if procedures_data:
            for i, proc in enumerate(procedures_data):
                logger.debug(f"  - Procedure {i+1}: {proc.get('name', 'Unknown')} at {proc.get('location', 'N/A')}")
        
        # Populate state with the structured data
        state["raw_note"] = encounter_facts
        
        # Clear any previous errors since we succeeded
        if "error" in state:
            del state["error"]
        if "error_details" in state:
            del state["error_details"]
        
        logger.info(f"Successfully extracted clinical data for note_id: {note_id}")
        
    except Exception as e:
        error_msg = f"Error extracting clinical data for note_id {note_id}: {str(e)}"
        logger.exception(error_msg)
        state["error"] = error_msg
        state["error_details"] = {
            "field": "raw_note",
            "reason": "extraction_error",
            "note_id": note_id,
            "exception": str(e)
        }
        state["raw_note"] = {}
    
    return state


# For testing
if __name__ == "__main__":
    import asyncio
    
    async def test():
        test_state: BillingState = {"note_id": 703862}  # type: ignore
        updated_state = await clinical_node(test_state)
        print(f"Raw note keys: {updated_state.get('raw_note', {}).keys()}")
        if updated_state.get("error"):
            print(f"Error: {updated_state['error']}")
    
    asyncio.run(test())
