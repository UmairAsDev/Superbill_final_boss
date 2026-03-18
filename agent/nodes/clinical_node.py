import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))
from context.note_context import structured_notes_context
from config.schema import BillingState
from loguru import logger


async def clinical_node(state: BillingState):
    note_id = state.get("note_id")
    encounter_facts = await structured_notes_context(note_id)
    logger.info(f"Extracted encounter facts: {encounter_facts}")
    if encounter_facts:
        state["raw_note"] = encounter_facts
    return state



# if __name__ == "__main__":
#     test_state = BillingState(note_id="703862")
#     updated_state = clinical_node(test_state)
#     print(updated_state["encounter_facts"])