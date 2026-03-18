import re
from bs4 import BeautifulSoup
from loguru import logger
import copy


def html_parser(html_content: str) -> str:
    if not isinstance(html_content, str):
        return ""
    text = BeautifulSoup(html_content, "html.parser").get_text(separator=" ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()




def clean_html(notes_data:list[dict]) -> list[dict]:
    """Clean the notes data by removing HTML tags."""
    
    try:
        if not notes_data or not isinstance(notes_data, list):
            raise ValueError("Invalid data passed to clean_html_tags_safe")


        cleaned = [dict(note) for note in notes_data]

        fields_to_clean = [
            "biopsyNotes",
            "examination",
            "patientSummary",
            "complaints",
            "currentmedication",
            "assesment",
            "procedure",
            "mohsNotes",
        ]

        for note in cleaned:
            logger.info(f"Cleaning HTML tags for note ID: {note.get('noteId', 'Unknown')}")
            
            for field in fields_to_clean:
                if field in note and note[field]:
                    note[field] = html_parser(note[field])

        return cleaned

    except Exception as e:
        logger.error(f"Error in clean_html_tags: {e}")
        return []
