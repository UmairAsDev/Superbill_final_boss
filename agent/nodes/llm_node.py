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
    raw_note = state.get("raw_note")

    if not raw_note:
        raise ValueError("No raw note found in state")

    llm = get_openai_llm()

    parser = PydanticOutputParser(pydantic_object=BillingOutput)

    prompt = billing_prompt.partial(
        format_instructions=parser.get_format_instructions()
    )
    print("Prompt template:", prompt)  # Debug: print the prompt template
    chain = prompt | llm | parser

    try:
        response: BillingOutput = chain.invoke({
            "raw_note": json.dumps(raw_note, default=str, indent=2)
        })
        print("LLM response:", response)
    except Exception as e:
        logger.error(f"LLM parsing failed: {e}")
        raise ValueError("LLM failed to return valid structured output")

    if response is None:
        raise ValueError("LLM returned empty response")

    llm_data = response.model_dump()

    required_keys = ["CPT_codes", "E_M_codes", "ICD10_codes", "procedure_details"]

    for key in required_keys:
        if key not in llm_data:
            raise ValueError(f"Missing key in LLM output: {key}")

    state["billing_response"] = llm_data

    return state