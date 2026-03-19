import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))
from agent.nodes.clinical_node import clinical_node
from agent.nodes.llm_node import llm_node
from agent.nodes.retrieval_node import retrieval_node
from agent.nodes.validator_node import cpt_validator_node, em_validator_node, icd_validator_node, normalization_node, output_layer
from agent.nodes.billing_node import superbill_node
from langgraph.graph import StateGraph, START, END
from config.schema import BillingState
from loguru import logger


# Maximum number of retries for LLM regeneration
MAX_RETRIES = 2


def should_retry_or_proceed(state: BillingState) -> str:
    """
    Routing function to determine if we should retry LLM generation or proceed.
    
    Checks:
    - If all CPT codes were rejected AND retry_count < MAX_RETRIES -> retry
    - Otherwise -> proceed to superbill
    
    Returns:
        "retry" or "proceed"
    """
    retry_count = state.get("retry_count", 0)  # type: ignore
    
    # Check if all CPT codes were rejected
    validated_cpt = state.get("validated_cpt", [])
    original_cpt = state.get("billing_response", {}).get("CPT_codes", [])
    all_cpt_rejected = len(original_cpt) > 0 and len(validated_cpt) == 0
    
    # Check if all E/M codes were rejected
    all_em_rejected = state.get("all_em_rejected", False)  # type: ignore
    
    # Decide if retry is needed
    should_retry = (all_cpt_rejected or all_em_rejected) and retry_count < MAX_RETRIES
    
    if should_retry:
        logger.warning(
            f"Validation rejected too many codes (CPT: {len(validated_cpt)}/{len(original_cpt)}, "
            f"E/M rejected: {all_em_rejected}). Retry {retry_count + 1}/{MAX_RETRIES}"
        )
        return "retry"
    
    if retry_count >= MAX_RETRIES:
        logger.warning(f"Max retries ({MAX_RETRIES}) reached. Proceeding with available codes.")
    
    logger.info(f"Validation passed. Proceeding to superbill generation.")
    return "proceed"


def increment_retry_and_prepare(state: BillingState) -> BillingState:
    """
    Increment retry counter and clear validation results for re-processing.
    """
    current_retry = state.get("retry_count", 0)  # type: ignore
    state["retry_count"] = current_retry + 1  # type: ignore
    
    # Clear previous validation results
    state["validated_cpt"] = []
    state["validated_em"] = []
    state["validated_icd"] = []
    
    logger.info(f"Retry #{state['retry_count']}: Clearing validation and re-invoking LLM")  # type: ignore
    
    return state


def superbill_graph():
    """
    Build and compile the superbill generation workflow graph.
    
    Flow:
    START → clinical → retrieval → llm → normalize → cpt_val → em_val → icd_val
          → (conditional: retry or proceed) → superbill → output_layer → END
    
    Retry logic:
    - After icd_val, check if too many codes were rejected
    - If so and retry_count < MAX_RETRIES, route back to llm
    - Otherwise proceed to superbill
    """
    workflow = StateGraph(BillingState)

    # --- Nodes ---
    # Clinical node: extracts encounter facts from note
    workflow.add_node("clinical", clinical_node)
    
    # Retrieval node: retrieves CPT/ICD candidates from vector DB
    workflow.add_node("retrieval", retrieval_node)

    # LLM node: generates suggested CPT, EM, Modifiers
    workflow.add_node("llm", llm_node)
    
    # Normalization node: ensures consistent structure
    workflow.add_node("normalize", normalization_node)

    # Validation nodes: validate LLM suggestions against DB
    workflow.add_node("cpt_val", cpt_validator_node)
    workflow.add_node("em_val", em_validator_node)
    workflow.add_node("icd_val", icd_validator_node)
    
    # Retry preparation node: increments counter and clears for retry
    workflow.add_node("retry_prep", increment_retry_and_prepare)

    # Superbill node: compile all validated codes into final bill
    workflow.add_node("superbill", superbill_node)
    
    # Output layer: final quality gate and filtering
    workflow.add_node("output_layer", output_layer)

    # --- Edges ---
    # Start with clinical extraction
    workflow.add_edge(START, "clinical")
    workflow.add_edge("clinical", "retrieval")
    workflow.add_edge("retrieval", "llm")

    # LLM output goes through normalization
    workflow.add_edge("llm", "normalize")
    workflow.add_edge("normalize", "cpt_val")

    # Sequential validation
    workflow.add_edge("cpt_val", "em_val")
    workflow.add_edge("em_val", "icd_val")
    
    # Conditional routing after ICD-10 validation
    workflow.add_conditional_edges(
        "icd_val",
        should_retry_or_proceed,
        {
            "retry": "retry_prep",
            "proceed": "superbill"
        }
    )
    
    # Retry goes back to LLM
    workflow.add_edge("retry_prep", "llm")
    
    # Superbill to output layer to END
    workflow.add_edge("superbill", "output_layer")
    workflow.add_edge("output_layer", END)

    return workflow.compile()
