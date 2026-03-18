import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))
from config.schema import BillingState



def superbill_node(state: BillingState):
    encounter_facts = state.get("encounter_facts", {})
    superbill = {
        "patient_id": encounter_facts.get("patient", {}).get("id"),
        "date_of_service": encounter_facts.get("visit", {}).get("date"),
        "place_of_service": encounter_facts.get("visit", {}).get("place_of_service"),
        "diagnoses": encounter_facts.get("diagnoses"),
        "cpt_codes": state.get("validated_cpt", []),
        "em_codes": state.get("validated_em", []),
        "billing_notes": state.get("billing_response", {})
    }
    state["superbill"] = superbill
    return state