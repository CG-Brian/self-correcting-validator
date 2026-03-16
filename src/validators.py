
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

PHONE_RE = re.compile(r"^\d{10,11}$")  # Korean mobile commonly 10~11 digits

@dataclass
class ValidationErrorItem:
    field: str
    code: str
    message: str

def normalize_phone(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    digits = re.sub(r"\D", "", value)  # keep digits only
    return digits if digits else None

def validate_ticket_dict(ticket: Dict[str, Any]) -> Tuple[bool, List[ValidationErrorItem], Dict[str, Any]]:
    """
    Validates additional business rules beyond Pydantic schema.
    Returns:
      (is_valid, errors, normalized_ticket)
    """
    errors: List[ValidationErrorItem] = []
    normalized = dict(ticket)

    # Normalize phone to digits-only
    phone = normalized.get("contact_phone")
    phone_norm = normalize_phone(phone)
    normalized["contact_phone"] = phone_norm

    if phone_norm is not None and not PHONE_RE.match(phone_norm):
        errors.append(ValidationErrorItem(
            field="contact_phone",
            code="format",
            message="Digits only, length must be 10~11 (e.g., 01012341234)."
        ))

    # Basic sanity checks for order_id (optional)
    order_id = normalized.get("order_id")
    if order_id is not None:
        s = str(order_id).strip()
        if len(s) < 4:
            errors.append(ValidationErrorItem(
                field="order_id",
                code="too_short",
                message="order_id seems too short; set to null if unknown."
            ))
        normalized["order_id"] = s

    # Product string cleanup
    product = normalized.get("product")
    if product is not None:
        p = str(product).strip()
        normalized["product"] = p if p else None

    # Summary sanity: should be informative
    summary = normalized.get("summary")
    if isinstance(summary, str):
        if len(summary.strip()) < 5:
            errors.append(ValidationErrorItem(
                field="summary",
                code="too_short",
                message="summary must be at least 5 characters."
            ))

    return (len(errors) == 0, errors, normalized)

def errors_to_dicts(errors: List[ValidationErrorItem]) -> List[Dict[str, str]]:
    return [{"field": e.field, "code": e.code, "message": e.message} for e in errors]
