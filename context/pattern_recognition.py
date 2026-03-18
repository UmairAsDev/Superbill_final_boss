
PROCEDURE_PATTERNS = {
    "biopsy": [r"\bbiopsy\b"],
    "mohs": [r"\bmohs\b"],
    "srt": [r"\bsrt\b", r"\bsuperficial radiation\b"],
    "cryotherapy": [r"\bcryotherapy\b", r"\bliquid nitrogen\b"],
    "botox": [r"\bbotox\b", r"\bneuromodulator\b"],
    "excision": [r"\bexcision\b"],
    "edc": [r"\bed&c\b", r"\belectrodesiccation\b"],
}
METHOD_PATTERNS = {
    "shave": [r"\bshave\b"],
    "punch": [r"\bpunch\b"],
    "excisional": [r"\bexcision\b"],
}

COSMETIC_PATTERNS = [
    r"\bbotox\b",
    r"\bneuromodulator\b",
    r"\bfiller\b",
    r"\baesthetic\b",
    r"\bwrinkles\b",
    r"\bcosmetic\b",
    r"\blip flip\b"
]


PROCEDURE_CATEGORIES = {
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

import re

def match_patterns(text, pattern_dict):
    found = []
    for label, patterns in pattern_dict.items():
        for p in patterns:
            if re.search(p, text):
                found.append(label)
                break
    return list(set(found))


def extract_counts(text):
    patterns = [
        r"(?:Quantity|lesions?)[:\s]*(\d+)",
        r"\b(\d+)\s*lesions?\b",
        r"\bx\s*(\d+)\b"
    ]

    results = []
    for p in patterns:
        results += re.findall(p, text)

    return list(set(int(x) for x in results)) if results else []




def extract_locations(text):
    return list(set(re.findall(
        r"\b(face|chest|back|arm|leg|scalp|neck)\b",
        text
    )))


def detect_flags(text):
    return {
        "cosmetic": any(re.search(p, text) for p in COSMETIC_PATTERNS),
        "mohs": bool(re.search(r"\bmohs\b", text)),
    }
    

def classify_procedure(proc):
    for category, items in PROCEDURE_CATEGORIES.items():
        if proc in items:
            return category
    return "unknown"

def extract_signals(structured_input):
    text = structured_input["normalized_text"]
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
    

def extract_stages(text):
    match = re.search(r"stage[s]?\s*(\d+)", text)
    return int(match.group(1)) if match else None


def extract_dose(text):
    match = re.search(r"(\d+)\s*(units|mg|ml)", text)
    return match.group(0) if match else None

    