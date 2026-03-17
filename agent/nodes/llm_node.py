import sys
import json
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))
from src.services.prompts import billing_prompt
from src.services.llm_factory import get_openai_llm
from config.schema import BillingState, BillingOutput
from langchain_core.output_parsers import PydanticOutputParser
from loguru import logger



    
def llm_node(state: BillingState):
    encounter_facts = state.get("encounter_facts")
    if not encounter_facts:
        raise ValueError("No encounter facts found in state")
    
    llm = get_openai_llm()

    parser = PydanticOutputParser(pydantic_object=BillingOutput)

    prompt = billing_prompt.partial(
        format_instructions=parser.get_format_instructions()
    )

    chain = prompt | llm | parser

    response_new = chain.invoke({
        "raw_note": state.get("encounter_facts", "")
    })
    logger.info(f"LLM response: {response_new}")
    response: BillingOutput = chain.invoke({
        "raw_note": state.get("encounter_facts", "")
    })


    if response is None:
        raise ValueError("LLM did not return a response")

    llm_data = response.model_dump()
    for key in ["E_M_codes", "CPT_codes", "ICD10_codes", "procedure_details"]:
        if key not in llm_data or llm_data[key] is None:
            llm_data[key] = [] if "codes" in key else {}

    state["billing_response"].update(llm_data)

    return state

