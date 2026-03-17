import asyncio
import os
import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent))
from src.notes.notes import notes
from loguru import logger
from sqldatabase.conn import async_engine
from utils.helper import clean_html
from operator import itemgetter











async def notes_context(note_id: int):
    try:
        note_data = await notes(note_id)
        cleaned_data = clean_html(note_data) if note_data else None
        return cleaned_data

    finally:
        await async_engine.dispose()
        logger.info("Database connection closed.")



def structured_notes_context(note_id: int): 
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        import nest_asyncio
        nest_asyncio.apply()
        notes = loop.run_until_complete(notes_context(note_id))
    except RuntimeError:
        notes = asyncio.run(notes_context(note_id))

    # Define all required fields with consistent naming
    required_fields = [
        ("noteDate", "noteDate"),
        ("patientId", "patientId"),
        ("PlaceOfService", "PlaceOfService"),
        ("patientSummary", "patientSummary"),
        ("complaints", "complaints"),
        ("assesment", "assesment"),
        ("diagnoses", "diagnoses"),
        ("procedure", "procedure"),
        ("examination", "examination"),
        ("pastHistory", "pastHistory"),
        ("currentmedication", "currentmedication"),
        ("biopsyNotes", "biopsyNotes"),
        ("mohsNotes", "mohsNotes"),
    ]

    # If no notes found, return all fields as None
    if not notes or not isinstance(notes, list) or not notes[0]:
        return {k: None for k, _ in required_fields}

    record = notes[0]
    encounter_facts = {k: record.get(db_key, None) for k, db_key in required_fields}
    return encounter_facts



if __name__ == "__main__":
    test_note_id = 577074
    result = structured_notes_context(test_note_id)
    print(result)