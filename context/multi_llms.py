import os
import sys
import pathlib
import re
import json
from datetime import datetime
from dotenv import load_dotenv
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


async def build_procedure_structure(state):
    return await client.chat.completions.acreate(
        model="gpt-4.1-mini",
        temperature=0.0,
        messages=[
            {"role": "system", "content": "You are a medical coding assistant. Extract structured procedure details from clinical notes."},
            {"role": "user", "content": PROCEDURE_PROMPT}
        ]
    )


async def build_diagnosis_structure(state):
    return await client.chat.completions.acreate(
        model="gpt-4.1-mini",
        temperature=0.0,
        messages=[
            {"role": "system", "content": "You are a medical coding assistant. Extract structured diagnosis details from clinical notes."},
            {"role": "user", "content": DIAGNOSIS_PROMPT}
        ]
    )


async def biopsy_mohs_structure(state):
    return await client.chat.completions.acreate(
        model="gpt-4.1-mini",
        temperature=0.0,
        messages=[
            {"role": "system", "content": "You are a medical coding assistant. Extract biopsy and mohs details from clinical notes."},
            {"role": "user", "content": BIOPSY_MOHS_PROMPT}
        ]
    )


async def assessment_structure(state):
    return await client.chat.completions.acreate(
        model="gpt-4.1-mini",
        temperature=0.0,
        messages=[
            {"role": "system", "content": "You are a medical coding assistant. Extract assessment details from clinical notes."},
            {"role": "user", "content": ASSESSMENT_PROMPT}
        ]
    )


def extract_mohs_details(sections):
    mohs_text = sections.get('mohs', '') or ''
    complaints = sections.get('complaints', '') or ''
    examination = sections.get('examination', '') or ''
    
    # Defect size
    defect_size = re.search(r'Post-Mohs Deficit Size: ([\d\.]+ x [\d\.]+) cm', mohs_text)
    defect_size = defect_size.group(1) if defect_size else None

    # Final closure size
    closure_size = re.search(r'final closure size is ([\d\.]+) cm', mohs_text, re.I)
    closure_size = closure_size.group(1) if closure_size else None

    # Closure type
    closure_type = 'Complex Closure' if re.search(r'Complex Closure', mohs_text, re.I) else None

    # Stages
    stages = re.findall(r'(\d+)(?:st|nd|rd|th)\s+Stage:\s+(\d+)\s+Sections?,\s*(Positive|Negative)', mohs_text, flags=re.I)
    mohs_stages = [{'stage': s[0], 'sections': s[1], 'result': s[2]} for s in stages]

    # Tumor type
    tumor_type = re.search(r'Tumor: ([A-Z\-]+)', complaints)
    tumor_type = tumor_type.group(1) if tumor_type else None

    # Biopsy date
    biopsy_date = re.search(r'Biopsy Date: ([\d/]+)', complaints)
    biopsy_date = biopsy_date.group(1) if biopsy_date else None

    # Location
    location = re.search(r'Location: ([A-Za-z ]+)', complaints)
    location = location.group(1) if location else None

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


async def extract_structured_note(note_id):
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

    # Parse JSON safely
    try:
        procedures = json.loads(procedure_result.choices[0].message.content).get("procedures", [])
    except:
        procedures = []

    try:
        diagnosis = json.loads(diagnosis_result.choices[0].message.content).get("diagnosis", [])
    except:
        diagnosis = []

    try:
        biopsy_mohs = json.loads(biopsy_mohs_result.choices[0].message.content)
    except:
        biopsy_mohs = {"biopsy": None, "mohs": None}

    try:
        assessment = json.loads(assessment_result.choices[0].message.content)
    except:
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
    import asyncio
    note_id = 708314
    structured_data = asyncio.run(extract_structured_note(note_id))
    print(json.dumps(structured_data, indent=2))