import asyncio
import os
import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent))
from src.notes.notes import notes
from loguru import logger
from utils.helper import clean_html
from operator import itemgetter






async def notes_context(note_id: int):
    note_data = await notes(note_id)
    cleaned_data = clean_html(note_data) if note_data else None
    return cleaned_data



async def structured_notes_context(note_id: int): 
    notes = await notes_context(note_id)
    if not notes:
        logger.warning(f"No note data found for note_id: {note_id}")
        return None
    
    record = notes[0] 
    
    raw = {
        "note_date" : record.get("noteDate"),
        "patient_id" : record.get("patientId"),
        "place_of_service": record.get("PlaceOfService"),
        "summary": record.get("patientSummary"),
        "complaints": record.get("complaints"),
        "assessment": record.get("assesment"),
        "diagnoses_raw": record.get("diagnoses"),
        "procedure_raw": record.get("procedure"),
        "exam": record.get("examination"),
        "history": record.get("pastHistory"),
        "medications_raw": record.get("currentmedication"),
    }
    
    structured = {
        "patient" : {
            "id": raw["patient_id"],
            "summary": raw["summary"],
        },
        "visit" : { 
            "date": raw["note_date"],
            "place_of_service": raw["place_of_service"],
        },
        "clinical": {
            "complaints": raw["complaints"],
            "assessment": raw["assessment"],
            "exam": raw["exam"],
        },
        "procedures": raw["procedure_raw"],
        "diagnoses": raw["diagnoses_raw"],
        "medications": raw["medications_raw"],
    }
    structured["raw_note"] = raw
    return structured   



if __name__ == "__main__":
    test_note_id = 698404
    result = asyncio.run(structured_notes_context(test_note_id))
    print(result)