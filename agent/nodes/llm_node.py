import sys
import json
import pathlib
import asyncio
import openai
sys.path.append(str(pathlib.Path(__file__).parent.parent.parent))
from src.services.prompts import billing_prompt
from src.services.llm_factory import get_openai_llm
from config.schema import BillingState, BillingOutput
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import ValidationError
from loguru import logger


async def llm_node(state: BillingState):
    raw_note = state.get("raw_note")

    if not raw_note:
        raise ValueError("No raw note found in state")

    llm = get_openai_llm()

    parser = PydanticOutputParser(pydantic_object=BillingOutput)

    prompt = billing_prompt.partial(
        format_instructions=parser.get_format_instructions()
    )
    logger.debug(f"Prompt template: {prompt}")
    chain = prompt | llm | parser

    # Retry logic with exponential backoff
    max_attempts = 3
    delays = [1, 2, 4]  # seconds
    response: BillingOutput | None = None

    for attempt in range(max_attempts):
        try:
            response = await chain.ainvoke({
                "raw_note": json.dumps(raw_note, default=str, indent=2)
            })
            logger.info(f"LLM response received on attempt {attempt + 1}")
            break
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error on attempt {attempt + 1}: {e}")
            if attempt < max_attempts - 1:
                await asyncio.sleep(delays[attempt])
            else:
                raise ValueError("LLM failed to return valid JSON after retries")
        except ValidationError as e:
            logger.error(f"Validation error on attempt {attempt + 1}: {e}")
            if attempt < max_attempts - 1:
                await asyncio.sleep(delays[attempt])
            else:
                raise ValueError("LLM output validation failed after retries")
        except openai.APIError as e:
            logger.error(f"OpenAI API error on attempt {attempt + 1}: {e}")
            if attempt < max_attempts - 1:
                await asyncio.sleep(delays[attempt])
            else:
                raise ValueError(f"OpenAI API error after retries: {e}")
        except Exception as e:
            logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
            if attempt < max_attempts - 1:
                await asyncio.sleep(delays[attempt])
            else:
                raise ValueError("LLM failed to return valid structured output")

    if response is None:
        raise ValueError("LLM returned empty response")

    llm_data = response.model_dump()

    # Validate required keys
    required_keys = ["CPT_codes", "E_M_codes", "ICD10_codes", "procedure_details"]

    for key in required_keys:
        if key not in llm_data:
            raise ValueError(f"Missing key in LLM output: {key}")

    # Validate CPT_codes is not empty
    cpt_codes = llm_data.get("CPT_codes", [])
    if not cpt_codes:
        logger.warning("CPT_codes list is empty in LLM output")

    # Validate each CPT code object has required fields and correct types
    for idx, code_obj in enumerate(cpt_codes):
        if not isinstance(code_obj, dict):
            logger.warning(f"CPT_codes[{idx}] is not a dict: {type(code_obj)}")
            continue

        # Check required fields
        if "code" not in code_obj:
            logger.warning(f"CPT_codes[{idx}] missing 'code' field")
        elif not isinstance(code_obj.get("code"), str):
            logger.warning(f"CPT_codes[{idx}].code should be string, got {type(code_obj.get('code'))}")

        if "description" not in code_obj:
            logger.warning(f"CPT_codes[{idx}] missing 'description' field")

        # Validate quantity type if present
        quantity = code_obj.get("quantity")
        if quantity is not None and not isinstance(quantity, int):
            logger.warning(f"CPT_codes[{idx}].quantity should be int or None, got {type(quantity)}")

    state["billing_response"] = llm_data

    return state
