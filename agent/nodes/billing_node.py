import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))
from config.schema import BillingState



def superbill_node(state: BillingState):
    superbill = {
        "patient_id": state["encounter_facts"]['patientId'],
        "date_of_service": state["encounter_facts"]["noteDate"],
        "place_of_service": state["encounter_facts"]["PlaceOfService"],
        "diagnoses": state["encounter_facts"]["diagnoses"],
        "cpt_codes": state.get("validated_cpt", []),
        "em_codes": state.get("validated_em", []),
        "billing_notes": state.get("billing_response", {})
    }
    state["superbill"] = superbill
    return state