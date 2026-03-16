
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from src.schemas import ComplaintTicket
from src.validators import validate_ticket_dict, errors_to_dicts

from src.llm import call_llm_json
from src.prompts import (
    SYSTEM_EXTRACT, SYSTEM_REVISE,
    build_extract_user, build_revise_user
)

def validate_with_schema_and_rules(candidate: Dict[str, Any]) -> Tuple[bool, List[Dict[str, str]], Optional[Dict[str, Any]]]:
    """
    1) Pydantic schema validation
    2) Business-rule validation (+ normalization)
    Returns (ok, errors, normalized_data_or_none)
    """
    errors: List[Dict[str, str]] = []

    # Step 1: Pydantic schema validation
    try:
        obj = ComplaintTicket.model_validate(candidate)
        data = obj.model_dump()
    except Exception as e:
        errors.append({"field": "schema", "code": "pydantic", "message": str(e)})
        return False, errors, None

    # Step 2: Rule validation (phone normalization etc.)
    ok2, rule_errors, normalized = validate_ticket_dict(data)
    errors.extend(errors_to_dicts(rule_errors))

    return (len(errors) == 0), errors, normalized

def extract_ticket(text: str) -> Dict[str, Any]:
    user = build_extract_user(text)
    return call_llm_json(SYSTEM_EXTRACT, user, temperature=0.0)

def revise_ticket(original_text: str, prev_json: Dict[str, Any], errors: List[Dict[str, str]]) -> Dict[str, Any]:
    user = build_revise_user(original_text, prev_json, errors)
    return call_llm_json(SYSTEM_REVISE, user, temperature=0.0)

def run_self_correcting(text: str, max_attempts: int = 3) -> Dict[str, Any]:
    """
    Returns:
      {
        ok: bool,
        attempts: int,
        final: dict or None,
        last_candidate: dict or None,
        errors: list,
        trace: [{attempt, candidate, ok, errors}]
      }
    """
    trace = []
    candidate: Optional[Dict[str, Any]] = None
    errors: List[Dict[str, str]] = []

    for attempt in range(1, max_attempts + 1):
        if attempt == 1:
            candidate = extract_ticket(text)
        else:
            candidate = revise_ticket(text, candidate or {}, errors)

        ok, errors, normalized = validate_with_schema_and_rules(candidate)
        trace.append({
            "attempt": attempt,
            "candidate": candidate,
            "ok": ok,
            "errors": errors,
            "normalized": normalized
        })

        if ok:
            return {
                "ok": True,
                "attempts": attempt,
                "final": normalized,
                "last_candidate": candidate,
                "errors": [],
                "trace": trace
            }

    return {
        "ok": False,
        "attempts": max_attempts,
        "final": None,
        "last_candidate": candidate,
        "errors": errors,
        "trace": trace
    }
