"""
Test script for billing pipeline nodes.

This script tests the clinical_node and llm_node with a sample note
to verify the async billing pipeline is working correctly.
"""

import asyncio
import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))

from agent.nodes.clinical_node import clinical_node
from agent.nodes.llm_node import llm_node
from config.schema import BillingState


async def test_nodes() -> None:
    """
    Test the billing pipeline nodes with a sample note.

    Creates a test BillingState with all required fields and runs
    it through the clinical_node and llm_node sequentially.
    """
    # Initialize test state with ALL BillingState fields
    test_state: BillingState = {
        "note_id": 703862,
        "raw_note": {},
        "billing_response": {},
        "validated_cpt": [],
        "validated_em": [],
        "validated_icd": [],
        "validated_modifiers": [],
        "retrieved_cpt": [],
        "retrieved_icd": [],
        "retrieval_context": "",
        "superbill": {},
        "retry_count": 0,
        "validation_errors": [],
        "all_em_rejected": False,
        "all_icd_rejected": False,
        "final_output": [],
        "error": None,
        "error_details": None,
    }

    # Clinical node (async)
    print("Running clinical node...")
    state_after_clinical = await clinical_node(test_state)
    print("After clinical node:", state_after_clinical.get("raw_note", {}).keys())

    # LLM node (async)
    print("\nRunning LLM node...")
    state_after_llm = await llm_node(state_after_clinical)
    print("After LLM node:", state_after_llm.get("billing_response", {}).keys())


if __name__ == "__main__":
    asyncio.run(test_nodes())
