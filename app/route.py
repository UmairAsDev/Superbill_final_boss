from fastapi import FastAPI, HTTPException, APIRouter
from pydantic import BaseModel
from typing import Dict
from agent.graph.biiling_graph import superbill_graph
from config.schema import BillingState

router = APIRouter()


class SuperbillRequest(BaseModel):
    note_id: int


class SuperbillResponse(BaseModel):
    superbill: Dict


workflow = superbill_graph()

@router.post("/generate-superbill", response_model=SuperbillResponse)
async def generate_superbill(request: SuperbillRequest):
    try:
        # Initialize state
        state: BillingState = {
            "note_id": request.note_id,
            "raw_note": {},
            "encounter_facts": {},
            "billing_response": {},
            "validated_cpt": [],
            "validated_em": [],
            "validated_modifiers": [],
            "superbill": {},
            # "final_output": {}
        }

        # Run workflow
        final_state = await  workflow.ainvoke(state)

        # Return only the superbill part
        return {"superbill": final_state["superbill"]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))