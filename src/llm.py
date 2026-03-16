
from __future__ import annotations
import json
import os
from typing import Any, Dict, Optional
from dotenv import load_dotenv

from openai import OpenAI

load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini") #Model namd and API key as Env variable
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def _extract_json(text: str) -> Dict[str, Any]: #Extracting JSON only
    """
    Try to parse the first valid JSON object from model output.
    Raises ValueError if parsing fails.
    """
    text = text.strip()
    # Common case: pure JSON
    try:
        return json.loads(text)
    except Exception:
        pass

    # Fallback: find JSON block between first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        chunk = text[start:end+1]
        return json.loads(chunk)

    raise ValueError("No JSON object found in model output.")

def call_llm_json(system: str, user: str, temperature: float = 0.0) -> Dict[str, Any]:
    """
    Calls OpenAI Chat Completions and returns parsed JSON object.
    """
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    content = resp.choices[0].message.content or ""
    return _extract_json(content)
