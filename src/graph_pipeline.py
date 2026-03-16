
from __future__ import annotations
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import StateGraph, END

# Reusing existing pipeline function
from src.pipeline import (
    extract_ticket,
    revise_ticket,
    validate_with_schema_and_rules,
)

# Reusing normalize logic from validators 
from src.validators import normalize_phone

class AgentState(TypedDict, total=False):
    text: str
    attempt: int
    max_attempts: int
    candidate: Dict[str, Any]
    errors: List[Dict[str, str]]
    normalized: Dict[str, Any]
    ok: bool
    trace: List[Dict[str, Any]]

def _init_trace(state: AgentState) -> None: # In case of no Trace
    if "trace" not in state or state["trace"] is None:
        state["trace"] = []

def extract_node(state: AgentState) -> AgentState:
    _init_trace(state)
    text = state["text"]
    state["candidate"] = extract_ticket(text)
    return state

def autofix_node(state: AgentState) -> AgentState: #Rule-first cheap fix
    """
    Cheap, deterministic cleanup BEFORE validation:
    - phone: digits-only normalize
    - trim strings
    - empty strings -> None
    """
    _init_trace(state)
    cand = dict(state.get("candidate") or {})

    def _clean_str(x):
        if x is None:
            return None
        s = str(x).strip()
        return s if s else None

    # Normalize/clean common fields
    cand["order_id"] = _clean_str(cand.get("order_id"))
    cand["product"] = _clean_str(cand.get("product"))
    cand["summary"] = _clean_str(cand.get("summary"))

    # phone digits-only
    cand["contact_phone"] = normalize_phone(cand.get("contact_phone"))

    state["candidate"] = cand

    state["trace"].append({
        "attempt": state.get("attempt", 1),
        "stage": "autofix",
        "note": "normalized phone/trimmed strings",
    })
    return state

def validate_node(state: AgentState) -> AgentState:
    _init_trace(state)
    candidate = state.get("candidate", {}) or {}
    ok, errors, normalized = validate_with_schema_and_rules(candidate)

    state["ok"] = ok
    state["errors"] = errors
    state["normalized"] = normalized if normalized is not None else {}

    state["trace"].append({
        "attempt": state.get("attempt", 1),
        "stage": "validate",
        "ok": ok,
        "errors": errors,
    })
    return state

def revise_node(state: AgentState) -> AgentState:
    _init_trace(state)
    text = state["text"]
    candidate = state.get("candidate", {}) or {}
    errors = state.get("errors", []) or []

    new_candidate = revise_ticket(text, candidate, errors)
    state["candidate"] = new_candidate
    state["attempt"] = int(state.get("attempt", 1)) + 1

    state["trace"].append({
        "attempt": state.get("attempt", 1),
        "stage": "revise",
        "note": "LLM revised using validation errors",
    })
    return state

def route_after_validate(state: AgentState) -> str:
    ok = bool(state.get("ok"))
    attempt = int(state.get("attempt", 1))
    max_attempts = int(state.get("max_attempts", 3))

    if ok:
        return "end"
    if attempt >= max_attempts:
        return "end"
    return "revise"

def build_graph():
    g = StateGraph(AgentState)

    g.add_node("extract", extract_node)
    g.add_node("autofix", autofix_node)
    g.add_node("validate", validate_node)
    g.add_node("revise", revise_node)

    g.set_entry_point("extract")

    # extract -> autofix -> validate
    g.add_edge("extract", "autofix")
    g.add_edge("autofix", "validate")

    # validate -> (revise or end)
    g.add_conditional_edges(
        "validate",
        route_after_validate,
        {
            "revise": "revise",
            "end": END,
        },
    )

    # revise -> autofix -> validate (루프)
    g.add_edge("revise", "autofix")

    return g.compile()

GRAPH = build_graph()

def run_langgraph(text: str, max_attempts: int = 3) -> Dict[str, Any]:
    state: AgentState = {
        "text": text,
        "attempt": 1,
        "max_attempts": max_attempts,
        "trace": [],
        "errors": [],
    }

    final = GRAPH.invoke(state)

    ok = bool(final.get("ok"))
    attempts = int(final.get("attempt", 1))

    return {
        "ok": ok,
        "attempts": attempts,
        "final": final.get("normalized") if ok else None,
        "last_candidate": final.get("candidate"),
        "errors": final.get("errors", []),
        "trace": final.get("trace", []),
    }
