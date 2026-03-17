import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))
from agent.nodes.clinical_node import clinical_node
from agent.nodes.llm_node import llm_node
from agent.nodes.billing_node import superbill_node
from config.schema import BillingState





def test_nodes():
    test_state = BillingState(note_id=703862) #type: ignore
    state_after_clinical = clinical_node(test_state)
    print("State after clinical node:", state_after_clinical)

    state_after_llm = llm_node(state_after_clinical)
    print("State after LLM node:", state_after_llm)
    
    
if __name__ == "__main__":
    test_nodes()
    