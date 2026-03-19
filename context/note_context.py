import asyncio
import os
import sys
import pathlib
import re
sys.path.append(str(pathlib.Path(__file__).parent.parent))
from src.notes.notes import notes
from loguru import logger
from utils.helper import clean_html
from operator import itemgetter
from typing import Dict, Any, List, Optional


def parse_procedure_details(procedure_raw: Optional[str]) -> List[Dict[str, Any]]:
    """Parse procedure raw text into structured format."""
    if not procedure_raw:
        return []
    
    procedures = []
    # Split by common delimiters (newlines, semicolons, or procedure markers)
    procedure_lines = re.split(r'[;\n]|\d+\.\s*', procedure_raw)
    
    for line in procedure_lines:
        line = line.strip()
        if not line:
            continue
        
        procedure = {
            "name": "",
            "quantity": 1,
            "location": "",
            "method": "",
            "details": line,
        }
        
        # Extract procedure name (first phrase or keyword)
        name_match = re.search(
            r'\b(biopsy|excision|mohs|cryotherapy|botox|injection|SRT|radiation|ED&C|electrodesiccation)\b',
            line, re.IGNORECASE
        )
        if name_match:
            procedure["name"] = name_match.group(1)
        
        # Extract quantity
        qty_match = re.search(r'(?:qty|quantity|x)\s*[:\s]*(\d+)', line, re.IGNORECASE)
        if qty_match:
            procedure["quantity"] = int(qty_match.group(1))
        else:
            # Try alternative pattern: "2 lesions"
            lesion_match = re.search(r'(\d+)\s*(?:lesions?|sites?|areas?)', line, re.IGNORECASE)
            if lesion_match:
                procedure["quantity"] = int(lesion_match.group(1))
        
        # Extract location/site
        loc_match = re.search(
            r'\b(face|chest|back|arm|leg|scalp|neck|forehead|nose|cheek|ear|lip|chin|shoulder|trunk|abdomen|hand|foot|finger|toe)\b',
            line, re.IGNORECASE
        )
        if loc_match:
            procedure["location"] = loc_match.group(1).lower()
        
        # Extract method
        method_match = re.search(r'\b(shave|punch|excisional|tangential)\b', line, re.IGNORECASE)
        if method_match:
            procedure["method"] = method_match.group(1).lower()
        
        procedures.append(procedure)
    
    return procedures if procedures else [{"name": "", "quantity": 1, "location": "", "method": "", "details": procedure_raw}]


def parse_diagnoses(diagnoses_raw: Optional[str]) -> List[Dict[str, Any]]:
    """Parse diagnoses raw text into structured format."""
    if not diagnoses_raw:
        return []
    
    diagnoses = []
    # Split by common delimiters
    diagnosis_items = re.split(r'[,;]|\n', diagnoses_raw)
    
    for item in diagnosis_items:
        item = item.strip()
        if not item:
            continue
        
        diagnosis = {
            "name": item,
            "code": "",
        }
        
        # Extract ICD-10 code if present (pattern like C44.xxx, L82.x, etc.)
        code_match = re.search(r'\b([A-Z]\d{2}(?:\.\d{1,4})?)\b', item)
        if code_match:
            diagnosis["code"] = code_match.group(1)
            # Remove code from name
            diagnosis["name"] = re.sub(r'\s*[A-Z]\d{2}(?:\.\d{1,4})?\s*', '', item).strip()
        
        diagnoses.append(diagnosis)
    
    return diagnoses


def parse_medications(medications_raw: Optional[str]) -> List[Dict[str, Any]]:
    """Parse medications raw text into structured format."""
    if not medications_raw:
        return []
    
    medications = []
    # Split by common delimiters
    med_items = re.split(r'[,;]|\n', medications_raw)
    
    for item in med_items:
        item = item.strip()
        if not item:
            continue
        
        medication = {
            "name": item,
            "dosage": "",
            "frequency": "",
        }
        
        # Extract dosage (pattern like 10mg, 500 mg, etc.)
        dosage_match = re.search(r'(\d+(?:\.\d+)?\s*(?:mg|ml|mcg|g|units?))', item, re.IGNORECASE)
        if dosage_match:
            medication["dosage"] = dosage_match.group(1)
        
        # Extract frequency
        freq_match = re.search(r'\b(daily|twice daily|bid|tid|qid|prn|as needed|weekly|monthly)\b', item, re.IGNORECASE)
        if freq_match:
            medication["frequency"] = freq_match.group(1).lower()
        
        medications.append(medication)
    
    return medications


async def notes_context(note_id: int):
    note_data = await notes(note_id)
    cleaned_data = clean_html(note_data) if note_data else None
    return cleaned_data


async def structured_notes_context(note_id: int) -> Dict[str, Any]:
    """
    Fetch and structure notes data for a given note_id.
    
    Returns a well-formed dict with structured data even if some fields are missing.
    """
    notes_data = await notes_context(note_id)
    
    # Return empty structured dict if no data
    if not notes_data:
        logger.warning(f"No note data found for note_id: {note_id}")
        return _empty_structured_response()
    
    record = notes_data[0] if isinstance(notes_data, list) and notes_data else {}
    
    if not record:
        logger.warning(f"Empty record for note_id: {note_id}")
        return _empty_structured_response()
    
    # Extract raw fields with defaults
    raw = {
        "note_date": record.get("noteDate"),
        "patient_id": record.get("patientId"),
        "place_of_service": record.get("PlaceOfService"),
        "summary": record.get("patientSummary"),
        "complaints": record.get("complaints"),
        "assessment": record.get("assessment") or record.get("assesment"),  # Handle both spellings
        "diagnoses_raw": record.get("diagnoses"),
        "procedure_raw": record.get("procedure"),
        "exam": record.get("examination"),
        "history": record.get("pastHistory"),
        "medications_raw": record.get("currentmedication"),
    }
    
    # Validate required fields
    missing_fields = []
    if not raw["complaints"]:
        missing_fields.append("complaints")
    if not raw["assessment"]:
        missing_fields.append("assessment")
    if not raw["procedure_raw"]:
        missing_fields.append("procedure_raw")
    
    if missing_fields:
        logger.warning(f"Missing required fields for note_id {note_id}: {missing_fields}")
    
    # Parse into structured data
    procedures_structured = parse_procedure_details(raw["procedure_raw"])
    diagnoses_structured = parse_diagnoses(raw["diagnoses_raw"])
    medications_structured = parse_medications(raw["medications_raw"])
    
    structured = {
        "patient": {
            "id": raw["patient_id"],
            "summary": raw["summary"] or "",
        },
        "visit": {
            "date": raw["note_date"],
            "place_of_service": raw["place_of_service"] or "",
        },
        "clinical": {
            "complaints": raw["complaints"] or "",
            "assessment": raw["assessment"] or "",
            "exam": raw["exam"] or "",
        },
        "procedures": procedures_structured,
        "diagnoses": diagnoses_structured,
        "medications": medications_structured,
        # Keep raw data for reference
        "procedures_raw": raw["procedure_raw"] or "",
        "diagnoses_raw": raw["diagnoses_raw"] or "",
        "medications_raw": raw["medications_raw"] or "",
    }
    structured["raw_note"] = raw
    return structured


def _empty_structured_response() -> Dict[str, Any]:
    """Return an empty but well-formed structured response."""
    return {
        "patient": {
            "id": None,
            "summary": "",
        },
        "visit": {
            "date": None,
            "place_of_service": "",
        },
        "clinical": {
            "complaints": "",
            "assessment": "",
            "exam": "",
        },
        "procedures": [],
        "diagnoses": [],
        "medications": [],
        "procedures_raw": "",
        "diagnoses_raw": "",
        "medications_raw": "",
        "raw_note": {},
    }


if __name__ == "__main__":
    test_note_id = 698404
    result = asyncio.run(structured_notes_context(test_note_id))
    print(result)
