"""
Strategy Analyzer — Gemini 2.5 Flash Pre-Analysis
===================================================
Before bombardment begins, sends the target system description to
Gemini 2.5 Flash to determine which mutation algorithms are most
effective for maximizing vulnerability discovery.

The API returns a JSON array of selected algorithm names.
"""

import os
import json
import re
import httpx
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()

# Gemini 2.5 Flash endpoint
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

# Map of display names → internal algorithm keys
ALGO_MAP = {
    "bit flip mutation": "bit_flip",
    "bit-flip mutation": "bit_flip",
    "bit flip": "bit_flip",
    "bitflip": "bit_flip",
    "arithmetic mutation": "arithmetic",
    "arithmetic": "arithmetic",
    "block-based mutation": "block",
    "block based mutation": "block",
    "block mutation": "block",
    "block": "block",
    "dictionary-based mutation": "dictionary",
    "dictionary based mutation": "dictionary",
    "dictionary mutation": "dictionary",
    "dictionary": "dictionary",
}

SYSTEM_PROMPT = """You are an expert fuzzing strategy engine.

Given a target system: {target_system}

Available mutation algorithms:
- Bit Flip Mutation
- Arithmetic Mutation
- Block-Based Mutation
- Dictionary-Based Mutation

Analyze the target system's input type and structure, and select only the most effective mutation algorithms.

Output ONLY a valid JSON array of selected algorithm names from the list above. DO NOT include markdown formatting (like ```json), DO NOT include conversational text (like "Here is the JSON"). Just the raw array.

Example output:
["Arithmetic Mutation", "Block-Based Mutation"]
"""


def _build_target_description(target_binary: str, seed_dir: str) -> str:
    """Auto-generate a target description from the binary and seed files."""
    desc_parts = [f"Binary: {os.path.basename(target_binary)}"]

    # Read seed files to infer input format
    if os.path.isdir(seed_dir):
        for fname in sorted(os.listdir(seed_dir))[:3]:
            fpath = os.path.join(seed_dir, fname)
            if os.path.isfile(fpath):
                try:
                    with open(fpath, "r") as f:
                        content = f.read(500)
                    desc_parts.append(f"Sample input ({fname}):\n{content}")
                except Exception:
                    pass

    # Try to read source if available
    src = target_binary.replace("vulnerable", "vulnerable.cpp")
    if not os.path.isfile(src):
        src = target_binary + ".cpp"
    if os.path.isfile(src):
        try:
            with open(src, "r") as f:
                source = f.read(2000)
            desc_parts.append(f"Source code (first 2000 chars):\n{source}")
        except Exception:
            pass

    return "\n\n".join(desc_parts)


def _parse_algorithms(response_text: str) -> List[str]:
    """
    Parse Gemini's response — expects a JSON array like:
    ["Arithmetic Mutation", "Block-Based Mutation"]
    Falls back to text matching if JSON parsing fails.
    """
    text = response_text.strip()
    
    # Strip common markdown blocks just in case
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    # Strategy 1: Try direct JSON parse
    try:
        arr = json.loads(text)
        if isinstance(arr, list):
            selected = []
            for item in arr:
                key = ALGO_MAP.get(item.lower().strip())
                if key and key not in selected:
                    selected.append(key)
            if selected:
                return selected
    except (json.JSONDecodeError, TypeError):
        pass

    # Strategy 2: Extract JSON array from surrounding text (e.g. ```json [...] ```)
    json_match = re.search(r'\[.*?\]', text, re.DOTALL)
    if json_match:
        try:
            arr = json.loads(json_match.group())
            if isinstance(arr, list):
                selected = []
                for item in arr:
                    key = ALGO_MAP.get(str(item).lower().strip())
                    if key and key not in selected:
                        selected.append(key)
                if selected:
                    return selected
        except (json.JSONDecodeError, TypeError):
            pass

    # Strategy 3: Fall back to text matching (backward-compat)
    text_lower = text.lower()
    selected = []
    # If the response was just a conversational mess, don't use the fallback
    # if it doesn't even contain the names. But actually, if it contains
    # the names as part of the prompt echo, it will match all.
    # Let's be strict: if it didn't parse as JSON array, we still fallback.
    for display_name, key in ALGO_MAP.items():
        if display_name in text_lower and key not in selected:
            selected.append(key)

    # Fallback: if nothing matched, use all algorithms
    if not selected:
        selected = ["bit_flip", "arithmetic", "block", "dictionary"]

    return selected


async def analyze_target(
    target_binary: str,
    seed_dir: str,
    custom_description: Optional[str] = None,
) -> dict:
    """
    Call Gemini 2.5 Flash to analyze the target and select algorithms.

    Returns:
        {
            "selected_algorithms": ["bit_flip", "dictionary", ...],
            "raw_response": "...",
            "target_description": "...",
            "status": "success" | "error" | "fallback"
        }
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return {
            "selected_algorithms": ["bit_flip", "arithmetic", "block", "dictionary"],
            "raw_response": "No API key configured — using all algorithms.",
            "target_description": "",
            "status": "fallback",
        }

    # Build target description
    if custom_description:
        target_desc = custom_description
    else:
        target_desc = _build_target_description(target_binary, seed_dir)

    # Compose the prompt
    prompt = SYSTEM_PROMPT.replace("{target_system}", target_desc)

    # Call Gemini API
    request_body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{GEMINI_URL}?key={api_key}",
                json=request_body,
                headers={"Content-Type": "application/json"},
            )

        if resp.status_code != 200:
            return {
                "selected_algorithms": ["bit_flip", "arithmetic", "block", "dictionary"],
                "raw_response": f"API error {resp.status_code}: {resp.text[:300]}",
                "target_description": target_desc,
                "status": "error",
            }

        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        algorithms = _parse_algorithms(text)

        return {
            "selected_algorithms": algorithms,
            "raw_response": text.strip(),
            "target_description": target_desc,
            "status": "success",
        }

    except Exception as e:
        return {
            "selected_algorithms": ["bit_flip", "arithmetic", "block", "dictionary"],
            "raw_response": f"Exception: {str(e)}",
            "target_description": target_desc,
            "status": "error",
        }
