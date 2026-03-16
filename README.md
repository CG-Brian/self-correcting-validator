# Self-Correcting Validator for Complaint Ticket Extraction

A lightweight LLM reliability project that converts free-form customer complaints into structured support tickets using **schema validation**, **rule-based checks**, and **error-guided self-correction**.

## Overview

Large language models can generate structured JSON from natural language, but raw outputs are often unreliable for downstream workflows.  
Fields may be missing, enums may be invalid, and formatting may break business constraints.

This project explores a simple but practical pattern for improving reliability:

1. Extract a structured ticket from free-form complaint text
2. Validate the output with a strict schema
3. Apply deterministic business-rule checks
4. Feed validation errors back into the model
5. Retry until the output becomes valid or the attempt limit is reached

The result is a **self-correcting extraction pipeline** designed for settings like customer support intake, complaint triage, and CRM ingestion.

---

## Why I Built This

I wanted to move beyond a basic “LLM returns JSON” demo and build a small system that treats model outputs as **probabilistic guesses**, not trusted data.

The main design goal was to separate:

- **generation** (LLM extraction / revision)
- **validation** (schema + business rules)

This makes the pipeline easier to debug, extend, and evaluate.

---

## Problem Setting

Input:
- free-form customer complaint text

Output:
- structured complaint ticket with constrained fields such as:
  - `issue_type`
  - `severity`
  - `order_id`
  - `product`
  - `requested_action`
  - `contact_phone`
  - `summary`

Challenge:
- even when an LLM produces JSON, the output may still fail downstream requirements:
  - invalid enum values
  - missing required fields
  - inconsistent formatting
  - non-normalized phone numbers
  - weak or overly long summaries

---

## System Design

### 1. Schema Layer
A `Pydantic` model defines the target contract for extracted tickets.

This enforces:
- required fields
- allowed enum values
- field constraints
- no unexpected extra keys

### 2. Rule-Based Validation Layer
After schema validation, additional deterministic checks are applied.

Examples:
- normalize phone numbers into digits-only format
- reject malformed values
- apply business-specific validation rules beyond schema constraints

### 3. Self-Correcting Loop
If validation fails:
- the pipeline collects structured error messages
- those errors are passed back into a revision prompt
- the model retries with explicit feedback

This creates an **error-guided retry loop** instead of relying on blind repetition.

### 4. LangGraph Version
In addition to the loop-based baseline, the project also includes a `LangGraph` version of the workflow.

This makes the control flow more explicit and easier to extend with future steps such as:
- human review
- moderation
- confidence routing
- escalation logic

---

## Architecture

```
Free-form complaint text
        ↓
LLM extraction
        ↓
Pydantic schema validation
        ↓
Rule-based validation / normalization
        ↓
If invalid: generate structured error feedback
        ↓
LLM revision
        ↓
Repeat until valid or max attempts reached
```

---

## Example Flow

#### Input:
```
“배송이 너무 늦어요. 주문번호 2023-9911. 빨리 보내주세요. 연락은 010-1234-1234”
```

#### First-pass candidate:

```
{
  "issue_type": "delivery_delay",
  "severity": "medium",
  "requested_action": "expedite_shipping",
  "contact_phone": "010-1234-1234",
  "order_id": "2023-9911",
  "product": null,
  "summary": "배송 지연으로 빠른 배송 요청"
}
```

#### Validation Issue

- `contact_phone` should be digits only

#### Revised / Normalized Output:
```
{
  "issue_type": "delivery_delay",
  "severity": "medium",
  "requested_action": "expedite_shipping",
  "contact_phone": "01012341234",
  "order_id": "2023-9911",
  "product": null,
  "summary": "배송 지연으로 빠른 조치를 요청한 고객 불만"
}
```

---

## Project Structure
```
self-correcting-validator/
├─ src/
│  ├─ schemas.py
│  ├─ validators.py
│  ├─ prompts.py
│  ├─ llm.py
│  ├─ pipeline.py
│  ├─ graph_pipeline.py
│  └─ eval.py
├─ app/
│  └─ streamlit_app.py
├─ data/
│  ├─ samples.jsonl
│  └─ hard_cases.jsonl
├─ eval/
│  └─ eval_results.jsonl
├─ notebooks/
│  └─ 00_quickstart_demo.ipynb
├─ .env.example
├─ requirements.txt
└─ README.md
```

---

## Notebook Demo

The notebook in `notebooks/00_quickstart_demo.ipynb` is intended as a quick walkthrough of the system:

1. schema sanity check
2. rule-based validation without LLM
3. self-correcting extraction loop
4. LangGraph workflow version
5. evaluation examples

The notebook is a **demo layer**, while the actual project logic lives in `src/`.

---

## Evaluation

This project includes a small evaluation pipeline to inspect:

- pass/fail rate
- number of attempts required
- common validation error types
- failure cases after max retries

Example questions this evaluation helps answer:

- How often does the first extraction pass validation?
- How much does self-correction improve final success rate?
- What kinds of errors are most common?

---

## What This Project Demonstrates

This project is less about building a large production system and more about demonstrating a design pattern for LLM output reliability.

Key ideas:

- strict structured output contracts
- deterministic validation before downstream use
- separating generation from validation
- retrying based on explicit errors rather than vague prompts
- representing the workflow as both a loop and a graph

---

## Limitations

Current limitations include:

- small-scale evaluation
- prompt-based correction rather than fine-tuned correction
- simple business rules
- no confidence scoring or human-in-the-loop review yet

These are intentional tradeoffs for a lightweight side project focused on clarity and system design.

---

## Future Improvements

Possible next steps:

- add stronger evaluation with labeled cases
- compare first-pass vs corrected pass rates more formally
- add confidence estimation / routing
- support multilingual complaint intake
- connect the output to a downstream dashboard or CRM mock workflow

---

Tech Stack

- Python
- Pydantic
- OpenAI API
- LangGraph
- Streamlit

---

Takeaway

This project started from a simple question:

**How do you make LLM-generated structured outputs safer to use in real workflows?**

My answer here was to combine:

- schema enforcement
- deterministic validation
- error-guided retry
- explicit orchestration

into a small but practical self-correcting pipeline.

