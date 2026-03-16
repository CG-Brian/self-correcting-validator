
from __future__ import annotations

SCHEMA_GUIDE = """
You must output a single JSON object that matches this schema.

Fields:
- issue_type: one of ["delivery_delay","refund","defect","payment","other"]
- severity: one of ["low","medium","high"]
- order_id: string or null
- product: string or null
- requested_action: one of ["refund","replace","expedite_shipping","contact_me","other"]
- contact_phone: string digits only (e.g., "01012341234") or null
- summary: short neutral Korean summary (5~240 chars)

Rules:
- Output JSON only. No markdown, no explanation.
- If information is missing or uncertain, use null.
- Never invent order_id/product/phone.
"""

SYSTEM_EXTRACT = "You are a careful information extraction engine. Follow the schema exactly."
SYSTEM_REVISE  = "You are a strict JSON repair engine. Fix validation errors with minimal changes."

def build_extract_user(text: str) -> str:
    return f"""{SCHEMA_GUIDE}

Input text:
{text}

Return ONLY the JSON object.
"""

def build_revise_user(original_text: str, prev_json: dict, errors: list) -> str:
    return f"""{SCHEMA_GUIDE}

Original input text:
{original_text}

Previous JSON (may be invalid):
{prev_json}

Validation errors to fix:
{errors}

Task:
- Fix ONLY what is necessary to satisfy the schema/rules.
- If a field cannot be supported by the input text, set it to null.
Return ONLY the corrected JSON object.
"""
