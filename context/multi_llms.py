"""
Multi-LLM extraction module for structured clinical note parsing.

This module provides alternative extraction paths for procedures, diagnoses,
biopsy/mohs details, and assessments from clinical notes. These functions
are available for future integration into the billing pipeline.
"""

import asyncio
import json
import os
import pathlib
import re
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from loguru import logger
from openai import OpenAI

sys.path.append(str(pathlib.Path(__file__).parent.parent))
from context.note_context import structured_notes_context

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ----------------------------
# Prompts
# ----------------------------
PROCEDURE_PROMPT = """
Extract ONLY procedures.

Rules:
- Do NOT extract diagnosis
- Do NOT infer
- Multiple procedures allowed

Return JSON:
{{
    "procedures": [
        {{
            "name": "",
            "type": "radiation|excision|biopsy|mohs|imaging|other",
            "method": "",
            "location": "",
            "quantity": 1,
            "details": "",
            "attributes": {{
                    "anatomic_location": "",
                    "lesion_count": null,
                    "drug_administered": null,
                    "drug_strength_mg_per_ml": null,
                    "drug_total_mg": null,
                    "drug_total_ml": null
            }}
        }}
    ]
}}
"""

DIAGNOSIS_PROMPT = """
Extract diagnosis ONLY.

Rules:
- Include confirmed diagnoses only
- Ignore symptoms unless explicitly diagnosis

Return JSON:
{{
    "diagnosis": [
        {{
            "text": "",
            "codes": [""],
            "confirmed": true
        }}
    ]
}}
"""

BIOPSY_MOHS_PROMPT = """
Extract biopsy and mohs procedures.

Rules:
- Only if explicitly present
- Do not duplicate procedures

Return JSON:
{{
    "biopsy": {{
        "method": "",
        "location": ""
    }} | null,
    "mohs": {{
        "stages": null,
        "location": ""
    }} | null
}}
"""

ASSESSMENT_PROMPT = """
Extract visit type, medications, and whether billable.

Return JSON:
{{
    "visit_type": [],
    "assessment": "",
    "billable": true | false,
    "medications": []
}}
"""


async def build_procedure_structure(state: Dict[str, Any]) -> Any:
    """
    Extract structured procedure details from clinical notes using LLM.

    Args:
        state: The current billing state containing clinical note data.

    Returns:
        OpenAI chat completion response with procedure extraction results.

    Note:
        This is an alternative extraction path available for future
        integration into the billing pipeline.
    """
    return await client.chat.completions.acreate(
        model="gpt-4.1-mini",
        temperature=0.0,
        messages=[
            {"role": "system", "content": "You are a medical coding assistant. Extract structured procedure details from clinical notes."},
            {"role": "user", "content": PROCEDURE_PROMPT}
        ]
    )


async def build_diagnosis_structure(state: Dict[str, Any]) -> Any:
    """
    Extract structured diagnosis details from clinical notes using LLM.

    Args:
        state: The current billing state containing clinical note data.

    Returns:
        OpenAI chat completion response with diagnosis extraction results.

    Note:
        This is an alternative extraction path available for future
        integration into the billing pipeline.
    """
    return await client.chat.completions.acreate(
        model="gpt-4.1-mini",
        temperature=0.0,
        messages=[
            {"role": "system", "content": "You are a medical coding assistant. Extract structured diagnosis details from clinical notes."},
            {"role": "user", "content": DIAGNOSIS_PROMPT}
        ]
    )


async def biopsy_mohs_structure(state: Dict[str, Any]) -> Any:
    """
    Extract biopsy and Mohs procedure details from clinical notes using LLM.

    Args:
        state: The current billing state containing clinical note data.

    Returns:
        OpenAI chat completion response with biopsy/Mohs extraction results.

    Note:
        This is an alternative extraction path available for future
        integration into the billing pipeline.
    """
    return await client.chat.completions.acreate(
        model="gpt-4.1-mini",
        temperature=0.0,
        messages=[
            {"role": "system", "content": "You are a medical coding assistant. Extract biopsy and mohs details from clinical notes."},
            {"role": "user", "content": BIOPSY_MOHS_PROMPT}
        ]
    )


async def assessment_structure(state: Dict[str, Any]) -> Any:
    """
    Extract assessment details (visit type, medications, billability) from clinical notes.

    Args:
        state: The current billing state containing clinical note data.

    Returns:
        OpenAI chat completion response with assessment extraction results.

    Note:
        This is an alternative extraction path available for future
        integration into the billing pipeline.
    """
    return await client.chat.completions.acreate(
        model="gpt-4.1-mini",
        temperature=0.0,
        messages=[
            {"role": "system", "content": "You are a medical coding assistant. Extract assessment details from clinical notes."},
            {"role": "user", "content": ASSESSMENT_PROMPT}
        ]
    )


def extract_mohs_details(sections: Dict[str, str]) -> Dict[str, Any]:
    """
    Extract Mohs surgery details using regex pattern matching.

    This function uses hybrid regex extraction for Mohs-specific fields
    that have consistent formatting in clinical notes.

    Args:
        sections: Dictionary of clinical note sections (mohs, complaints, examination).

    Returns:
        Dictionary containing extracted Mohs details:
        - defect_size: Post-Mohs deficit dimensions
        - closure_size: Final closure size in cm
        - closure_type: Type of closure (e.g., Complex Closure)
        - mohs_stages: List of stage results with section counts
        - tumor_type: Type of tumor
        - biopsy_date: Date of original biopsy
        - location: Anatomic location
        - lesion_description: Description from examination

    Note:
        This is an alternative extraction path available for future
        integration into the billing pipeline.
    """
    mohs_text = sections.get('mohs', '') or ''
    complaints = sections.get('complaints', '') or ''
    examination = sections.get('examination', '') or ''

    # Defect size
    defect_match = re.search(r'Post-Mohs Deficit Size: ([\d\.]+ x [\d\.]+) cm', mohs_text)
    defect_size = defect_match.group(1) if defect_match else None

    # Final closure size
    closure_match = re.search(r'final closure size is ([\d\.]+) cm', mohs_text, re.I)
    closure_size = closure_match.group(1) if closure_match else None

    # Closure type
    closure_type = 'Complex Closure' if re.search(r'Complex Closure', mohs_text, re.I) else None

    # Stages
    stages = re.findall(r'(\d+)(?:st|nd|rd|th)\s+Stage:\s+(\d+)\s+Sections?,\s*(Positive|Negative)', mohs_text, flags=re.I)
    mohs_stages = [{'stage': s[0], 'sections': s[1], 'result': s[2]} for s in stages]

    # Tumor type
    tumor_match = re.search(r'Tumor: ([A-Z\-]+)', complaints)
    tumor_type = tumor_match.group(1) if tumor_match else None

    # Biopsy date
    biopsy_match = re.search(r'Biopsy Date: ([\d/]+)', complaints)
    biopsy_date = biopsy_match.group(1) if biopsy_match else None

    # Location
    location_match = re.search(r'Location: ([A-Za-z ]+)', complaints)
    location = location_match.group(1) if location_match else None

    # Lesion description
    lesion_desc = examination

    return {
        'defect_size': defect_size,
        'closure_size': closure_size,
        'closure_type': closure_type,
        'mohs_stages': mohs_stages,
        'tumor_type': tumor_type,
        'biopsy_date': biopsy_date,
        'location': location,
        'lesion_description': lesion_desc,
    }


async def extract_structured_note(note_id: int) -> Dict[str, Any]:
    """
    Extract all structured data from a clinical note using hybrid LLM + regex approach.

    This function orchestrates multiple parallel LLM calls for procedures, diagnoses,
    biopsy/mohs details, and assessments, then merges with regex-based Mohs extraction.

    Args:
        note_id: The unique identifier of the clinical note to process.

    Returns:
        Dictionary containing:
        - procedures: List of extracted procedures
        - diagnosis: List of extracted diagnoses
        - biopsy_mohs: Biopsy and Mohs details (merged with regex extraction)
        - assessment: Visit type, medications, and billability info
        - note_id: The original note identifier

    Note:
        This is an alternative extraction path available for future
        integration into the billing pipeline.
    """
    state = await structured_notes_context(note_id)
    sections = state.get("sections", {})

    # Hybrid Mohs extraction
    mohs_details = extract_mohs_details(sections)

    # LLM-based extraction
    procedure_result, diagnosis_result, biopsy_mohs_result, assessment_result = await asyncio.gather(
        build_procedure_structure(state),
        build_diagnosis_structure(state),
        biopsy_mohs_structure(state),
        assessment_structure(state)
    )

    # Parse JSON safely with specific exception handling
    try:
        procedures = json.loads(procedure_result.choices[0].message.content).get("procedures", [])
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse procedures JSON: {e}")
        procedures = []
    except Exception as e:
        logger.error(f"Unexpected error parsing procedures: {e}")
        procedures = []

    try:
        diagnosis = json.loads(diagnosis_result.choices[0].message.content).get("diagnosis", [])
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse diagnosis JSON: {e}")
        diagnosis = []
    except Exception as e:
        logger.error(f"Unexpected error parsing diagnosis: {e}")
        diagnosis = []

    try:
        biopsy_mohs = json.loads(biopsy_mohs_result.choices[0].message.content)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse biopsy_mohs JSON: {e}")
        biopsy_mohs = {"biopsy": None, "mohs": None}
    except Exception as e:
        logger.error(f"Unexpected error parsing biopsy_mohs: {e}")
        biopsy_mohs = {"biopsy": None, "mohs": None}

    try:
        assessment = json.loads(assessment_result.choices[0].message.content)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse assessment JSON: {e}")
        assessment = {}
    except Exception as e:
        logger.error(f"Unexpected error parsing assessment: {e}")
        assessment = {}

    # Merge hybrid Mohs details
    if biopsy_mohs.get("mohs"):
        biopsy_mohs["mohs"].update(mohs_details)

    return {
        "procedures": procedures,
        "diagnosis": diagnosis,
        "biopsy_mohs": biopsy_mohs,
        "assessment": assessment,
        "note_id": note_id
    }


if __name__ == "__main__":
    note_id = 708314
    structured_data = asyncio.run(extract_structured_note(note_id))
    print(json.dumps(structured_data, indent=2))
