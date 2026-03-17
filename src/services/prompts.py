from langchain_core.prompts import ChatPromptTemplate





billing_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You are a US dermatology medical billing expert. You are given a dermatology encounter note, and your task is to extract the relevant billing information from the note and return it in a structured format. Apply the  ICD-10, CPT, E/M coding and modifiers guidelines to identify the appropriate codes based on the documented procedures, patient type, closure type, closure size, and lesion size. If any of this information is missing or not applicable, return null for that field."),
        ("user", """Here is the encounter note:\n{raw_note} analyze the patient data. Return only a valid json
                 for example: {{
            "CPT_codes": [
                {{
                "code": "string",
                "description": "string",
                "units": 1,
                "modifiers": [],
                "linked_icd10": ["string"],
                "billing_party": "INS|PAT|NC|"
                }}
            ],
            "E_M_codes": [
                {{
                "code": "string",
                "description": "string",
                "units": 1,
                "modifiers": [],
                "linked_icd10": ["string"],
                "billing_party": "INS|PAT|NC|"
                }}
            ],
            "ICD10_codes": [],
            "procedure_details": {{}}
        }}"""
        )
    ]
)




