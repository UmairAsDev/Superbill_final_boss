import re
from typing import Dict, List, Any, Optional

# Compile all patterns with IGNORECASE at module level for efficiency
PROCEDURE_PATTERNS: Dict[str, List[re.Pattern]] = {
    "biopsy": [re.compile(r"\bbiopsy\b", re.IGNORECASE)],
    "mohs": [re.compile(r"\bmohs\b", re.IGNORECASE)],
    "srt": [re.compile(r"\bsrt\b", re.IGNORECASE), re.compile(r"\bsuperficial radiation\b", re.IGNORECASE)],
    "cryotherapy": [re.compile(r"\bcryotherapy\b", re.IGNORECASE), re.compile(r"\bliquid nitrogen\b", re.IGNORECASE)],
    "botox": [re.compile(r"\bbotox\b", re.IGNORECASE), re.compile(r"\bneuromodulator\b", re.IGNORECASE)],
    "excision": [re.compile(r"\bexcision\b", re.IGNORECASE)],
    "edc": [re.compile(r"\bed&c\b", re.IGNORECASE), re.compile(r"\belectrodesiccation\b", re.IGNORECASE)],
}

METHOD_PATTERNS: Dict[str, List[re.Pattern]] = {
    "shave": [re.compile(r"\bshave\b", re.IGNORECASE)],
    "punch": [re.compile(r"\bpunch\b", re.IGNORECASE)],
    "excisional": [re.compile(r"\bexcision\b", re.IGNORECASE)],
}

COSMETIC_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bbotox\b", re.IGNORECASE),
    re.compile(r"\bneuromodulator\b", re.IGNORECASE),
    re.compile(r"\bfiller\b", re.IGNORECASE),
    re.compile(r"\baesthetic\b", re.IGNORECASE),
    re.compile(r"\bwrinkles\b", re.IGNORECASE),
    re.compile(r"\bcosmetic\b", re.IGNORECASE),
    re.compile(r"\blip flip\b", re.IGNORECASE),
]

DIAGNOSIS_PATTERNS: Dict[str, List[re.Pattern]] = {
    "basal_cell_carcinoma": [
        re.compile(r"\bbasal cell carcinoma\b", re.IGNORECASE),
        re.compile(r"\bbcc\b", re.IGNORECASE),
    ],
    "squamous_cell_carcinoma": [
        re.compile(r"\bsquamous cell carcinoma\b", re.IGNORECASE),
        re.compile(r"\bscc\b", re.IGNORECASE),
    ],
    "melanoma": [
        re.compile(r"\bmelanoma\b", re.IGNORECASE),
    ],
    "actinic_keratosis": [
        re.compile(r"\bactinic keratosis\b", re.IGNORECASE),
        re.compile(r"\bak\b", re.IGNORECASE),
    ],
    "seborrheic_keratosis": [
        re.compile(r"\bseborrheic keratosis\b", re.IGNORECASE),
        re.compile(r"\bsk\b", re.IGNORECASE),
    ],
}

PROCEDURE_CATEGORIES: Dict[str, List[str]] = {
    "surgical": [
        "biopsy", "excision", "mohs", "edc"
    ],
    "destruction": [
        "cryotherapy", "laser", "chemical peel"
    ],
    "injection": [
        "intralesional", "steroid injection"
    ],
    "neuromodulator": [
        "botox", "dysport", "xeomin"
    ],
    "radiation": [
        "srt", "superficial radiation therapy"
    ]
}

# Pre-compiled patterns for extraction functions
_COUNT_PATTERNS: List[re.Pattern] = [
    re.compile(r"(?:Quantity|lesions?)[:\s]*(\d+)", re.IGNORECASE),
    re.compile(r"\b(\d+)\s*lesions?\b", re.IGNORECASE),
    re.compile(r"\bx\s*(\d+)\b", re.IGNORECASE),
]

_LOCATION_PATTERN: re.Pattern = re.compile(
    r"\b(face|chest|back|arm|leg|scalp|neck|forehead|nose|cheek|ear|shoulder|trunk|abdomen)\b",
    re.IGNORECASE
)

_STAGE_PATTERN: re.Pattern = re.compile(r"stage[s]?\s*(\d+)", re.IGNORECASE)

_DOSE_PATTERN: re.Pattern = re.compile(r"(\d+)\s*(units|mg|ml)", re.IGNORECASE)

_MOHS_PATTERN: re.Pattern = re.compile(r"\bmohs\b", re.IGNORECASE)


def match_patterns(text: str, pattern_dict: Dict[str, List[re.Pattern]]) -> List[str]:
    """Match text against a dictionary of compiled patterns."""
    if not text:
        return []
    
    found = []
    for label, patterns in pattern_dict.items():
        for p in patterns:
            if p.search(text):
                found.append(label)
                break
    return list(set(found))


def extract_counts(text: str) -> List[int]:
    """Extract quantity/count values from text using case-insensitive patterns."""
    if not text:
        return []
    
    results = []
    for p in _COUNT_PATTERNS:
        results += p.findall(text)
    
    return list(set(int(x) for x in results)) if results else []


def extract_locations(text: str) -> List[str]:
    """Extract anatomic locations from text using case-insensitive matching."""
    if not text:
        return []
    
    matches = _LOCATION_PATTERN.findall(text)
    return list(set(loc.lower() for loc in matches))


def detect_flags(text: str) -> Dict[str, bool]:
    """
    Detect special flags in text using case-insensitive matching.
    Checks for cosmetic procedures, mohs, and other procedure patterns.
    """
    if not text:
        return {
            "cosmetic": False,
            "mohs": False,
            "biopsy": False,
            "excision": False,
            "cryotherapy": False,
        }
    
    return {
        "cosmetic": any(p.search(text) for p in COSMETIC_PATTERNS),
        "mohs": bool(_MOHS_PATTERN.search(text)),
        "biopsy": any(p.search(text) for p in PROCEDURE_PATTERNS.get("biopsy", [])),
        "excision": any(p.search(text) for p in PROCEDURE_PATTERNS.get("excision", [])),
        "cryotherapy": any(p.search(text) for p in PROCEDURE_PATTERNS.get("cryotherapy", [])),
    }


def classify_procedure(proc: str) -> str:
    """Classify a procedure into its category."""
    proc_lower = proc.lower() if proc else ""
    for category, items in PROCEDURE_CATEGORIES.items():
        if proc_lower in [item.lower() for item in items]:
            return category
    return "unknown"


def extract_signals(structured_input: Dict[str, Any]) -> Dict[str, Any]:
    """Extract all clinical signals from structured input."""
    text = structured_input.get("normalized_text", "")
    
    if not text:
        return {
            "procedures": [],
            "categories": [],
            "methods": [],
            "counts": [],
            "locations": [],
            "stages": None,
            "dose": None,
            "flags": detect_flags(""),
            "confidence": {
                "procedure_detected": False,
            }
        }
    
    procedures = match_patterns(text, PROCEDURE_PATTERNS)
    return {
        "procedures": procedures,
        "categories": [classify_procedure(p) for p in procedures],
        "methods": match_patterns(text, METHOD_PATTERNS),
        "counts": extract_counts(text),
        "locations": extract_locations(text),
        "stages": extract_stages(text),
        "dose": extract_dose(text),
        "flags": detect_flags(text),
        "confidence": {
            "procedure_detected": len(procedures) > 0,
        }
    }


def extract_stages(text: str) -> Optional[int]:
    """Extract stage count from text using case-insensitive matching."""
    if not text:
        return None
    
    match = _STAGE_PATTERN.search(text)
    return int(match.group(1)) if match else None


def extract_dose(text: str) -> Optional[str]:
    """Extract dosage information from text using case-insensitive matching."""
    if not text:
        return None
    
    match = _DOSE_PATTERN.search(text)
    return match.group(0) if match else None


def match_diagnoses(text: str) -> List[str]:
    """Match text against diagnosis patterns (case-insensitive)."""
    return match_patterns(text, DIAGNOSIS_PATTERNS)
