import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))
from agent.nodes.clinical_node import clinical_node
from agent.nodes.llm_node import llm_node
from agent.nodes.validator_node import cpt_validator_node, em_validator_node, normalization_node
from agent.nodes.billing_node import superbill_node
from langgraph.graph import StateGraph, START, END
from config.schema import BillingState

import logging

# Setup logger
logger = logging.getLogger("superbill_graph")
logger.setLevel(logging.INFO)

def superbill_graph():

    workflow = StateGraph(BillingState)

    # --- Nodes ---
    # Clinical node: extracts encounter facts from note
    workflow.add_node("clinical", clinical_node)

    # LLM node: generates suggested CPT, EM, Modifiers
    workflow.add_node("llm", llm_node)
    workflow.add_node("normalize", normalization_node)

    # Validation nodes: validate LLM suggestions against DB
    workflow.add_node("cpt_val", cpt_validator_node)
    workflow.add_node("em_val", em_validator_node)

    # Superbill node: compile all validated codes into final bill
    workflow.add_node("superbill", superbill_node)

    # --- Edges ---
    workflow.add_edge(START, "clinical")
    workflow.add_edge("clinical", "llm")

    # (Optional but recommended if you added normalization node)
    workflow.add_edge("llm", "normalize")
    workflow.add_edge("normalize", "cpt_val")

    # Sequential validation (fixes your concurrency issue)
    workflow.add_edge("cpt_val", "em_val")
    workflow.add_edge("em_val", "superbill")

    workflow.add_edge("superbill", END)
        # workflow.add_edge("mod_val", "superbill") --- IGNORE ---

    return workflow.compile()
