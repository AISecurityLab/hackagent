# Copyright 2025 - AI4I. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Helpers for parsing attacker outputs into prompt data."""

import json
import re
from typing import Dict, Optional


def extract_prompt_and_improvement(content: str) -> Optional[Dict[str, str]]:
    """
    Extract a prompt (+ optional improvement) from attacker output.

    Supports direct JSON, JSON code blocks, regex extraction, and a
    plain-text fallback when no JSON structure is present.
    """
    if not content:
        return None

    raw = content.strip()

    for candidate in _candidate_json_strings(raw):
        parsed = _parse_json_prompt(candidate)
        if parsed:
            return parsed

    prompt_match = re.search(
        r'"prompt"\s*:\s*"((?:[^"\\]|\\.)*)"|'
        r"'prompt'\s*:\s*'((?:[^'\\]|\\.)*)'",
        raw,
        re.DOTALL,
    )
    improvement_match = re.search(
        r'"improvement"\s*:\s*"((?:[^"\\]|\\.)*)"|'
        r"'improvement'\s*:\s*'((?:[^'\\]|\\.)*)'",
        raw,
        re.DOTALL,
    )
    if prompt_match:
        prompt = prompt_match.group(1) or prompt_match.group(2) or ""
        prompt = _unescape_text(prompt)
        improvement = ""
        if improvement_match:
            improvement_value = improvement_match.group(1) or improvement_match.group(2)
            if improvement_value:
                improvement = _unescape_text(improvement_value)
        return {"prompt": prompt, "improvement": improvement}

    if not raw.startswith("{") and not raw.startswith("[") and len(raw) > 20:
        return {"prompt": raw, "improvement": ""}

    return None


def extract_prompt(content: str) -> Optional[str]:
    """Extract just the prompt string from attacker output."""
    parsed = extract_prompt_and_improvement(content)
    if not parsed:
        return None
    return parsed.get("prompt") or None


def _candidate_json_strings(raw: str) -> list:
    candidates = [raw]
    code_block_match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw, re.DOTALL)
    if code_block_match:
        candidates.append(code_block_match.group(1).strip())
    return candidates


def _parse_json_prompt(raw: str) -> Optional[Dict[str, str]]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, dict):
        return None

    prompt = parsed.get("prompt")
    if not prompt:
        return None

    return {
        "prompt": prompt,
        "improvement": parsed.get("improvement", ""),
    }


def _unescape_text(value: str) -> str:
    try:
        return value.encode().decode("unicode_escape")
    except Exception:
        return value
