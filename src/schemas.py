
from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

class IssueType(str, Enum):
    delivery_delay = "delivery_delay"
    refund = "refund"
    defect = "defect"
    payment = "payment"
    other = "other"

class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"

class RequestedAction(str, Enum):
    refund = "refund"
    replace = "replace"
    expedite_shipping = "expedite_shipping"
    contact_me = "contact_me"
    other = "other"

class ComplaintTicket(BaseModel):
    """
    Structured ticket extracted from free-form customer complaint text.
    """
    model_config = ConfigDict(extra="forbid")  # unexpected fields not allowed

    issue_type: IssueType = Field(..., description="Primary complaint category")
    severity: Severity = Field(..., description="Urgency/seriousness level")

    order_id: Optional[str] = Field(None, description="Order identifier if present")
    product: Optional[str] = Field(None, description="Product name/category if present")

    requested_action: RequestedAction = Field(..., description="What customer wants us to do")
    contact_phone: Optional[str] = Field(
        None,
        description="Digits only, no hyphens. Example: 01012341234"
    )

    summary: str = Field(..., min_length=5, max_length=240, description="Short neutral summary")
