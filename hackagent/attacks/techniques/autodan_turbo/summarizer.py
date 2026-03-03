# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Strategy summarizer — mirrors original summarizer.py (summarize + wrapper)."""

import json
import re

from hackagent.attacks.shared.response_utils import extract_response_content

from .config import (
    SUMMARIZER_SYSTEM_PROMPT,
    SUMMARIZER_WRAPPER_SYSTEM_PROMPT,
)
from .log_styles import format_phase_message


def _truncate_for_log(text: str, limit: int = 280) -> str:
    """Sanitize and truncate long payloads for concise logs.

    Args:
        text: Input content to log.
        limit: Maximum displayed character length.

    Returns:
        Single-line string capped to ``limit`` with optional ellipsis.
    """
    if text is None:
        return ""
    value = str(text).replace("\n", "\\n")
    if len(value) <= limit:
        return value
    return value[:limit] + "..."


def _extract_json_dict(text: str) -> dict | None:
    """Parse strategy JSON from potentially noisy model output.

    Paper mapping: supports the summarizer wrapper step that must output a JSON
    object containing ``Strategy`` and ``Definition``.

    Args:
        text: Wrapper output text potentially containing extra tokens/prefixes.

    Returns:
        Parsed dictionary when extraction succeeds, otherwise ``None``.
    """
    # Try the whole text first
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except (json.JSONDecodeError, ValueError):
        pass

    # Find first '{' and last '}' and try that substring
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, ValueError):
            pass

    # Regex fallback: extract Strategy and Definition values
    strat_m = re.search(r'"Strategy"\s*:\s*"([^"]+)"', text)
    defn_m = re.search(r'"Definition"\s*:\s*"([^"]+)"', text)
    if strat_m and defn_m:
        return {"Strategy": strat_m.group(1), "Definition": defn_m.group(1)}

    return None


def summarize_strategy(
    router,
    key,
    request,
    weak_prompt,
    strong_prompt,
    library,
    logger,
    max_retries=5,
    role_label="summarizer",
):
    """Summarize why a stronger prompt outperforms a weaker one.

    Paper mapping: this is the Summarizer LLM component. It compares
    weak/strong prompt pairs and extracts a reusable jailbreak strategy via a
    second wrapper pass that enforces structured JSON output.

    Args:
        router: Router bound to summarizer model.
        key: Registration key for summarizer route.
        request: Original attack goal used for prompt context.
        weak_prompt: Lower-scoring prompt candidate.
        strong_prompt: Higher-scoring prompt candidate.
        library: Existing strategy pool for duplicate-aware summarization.
        logger: Logger for summarization diagnostics.
        max_retries: Maximum attempts for valid strategy extraction.
        role_label: Log role label.

    Returns:
        Dictionary with at least ``Strategy`` and ``Definition`` on success,
        else ``None`` when extraction fails.
    """
    goal = f"making the target LLM provide a detailed answer to the request '{request}', rather than issuing a refusal."
    existing = json.dumps(
        [
            {"Strategy": v["Strategy"], "Definition": v["Definition"]}
            for v in library.values()
        ],
        indent=4,
        ensure_ascii=False,
    )
    system = SUMMARIZER_SYSTEM_PROMPT.format(
        existing_strategies=existing,
        goal=goal,
        weak_prompt=weak_prompt,
        strong_prompt=strong_prompt,
    )
    logger.info(
        format_phase_message(
            "summarize",
            f"[Role:{role_label}] summarizer_system_prompt='{_truncate_for_log(system)}'",
        )
    )

    for attempt in range(max_retries):
        try:
            # Step 1: Summarizer analysis (no assistant prefill for compatibility)
            msgs = [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": "Please adhere to the system message and provide your response.",
                },
            ]
            resp = router.route_request(
                registration_key=key,
                request_data={
                    "messages": msgs,
                    "max_tokens": 4096,
                    "temperature": 0.6,
                    "top_p": 0.9,
                },
            )
            analysis = extract_response_content(resp, logger)
            if not analysis:
                continue
            logger.info(
                format_phase_message(
                    "summarize",
                    f"[Role:{role_label}] summarizer_analysis='{_truncate_for_log(analysis)}'",
                )
            )

            # Step 2: Extract JSON (wrapper)
            msgs2 = [
                {"role": "system", "content": SUMMARIZER_WRAPPER_SYSTEM_PROMPT},
                {"role": "user", "content": f"[INPUT]: '{analysis}'"},
            ]
            resp2 = router.route_request(
                registration_key=key,
                request_data={
                    "messages": msgs2,
                    "max_tokens": 2000,
                    "temperature": 0.0,
                },
            )
            json_text = extract_response_content(resp2, logger)
            if not json_text:
                continue
            logger.info(
                format_phase_message(
                    "summarize",
                    f"[Role:{role_label}] summarizer_wrapper='{_truncate_for_log(json_text)}'",
                )
            )

            strategy = _extract_json_dict(json_text)
            if strategy and "Strategy" in strategy and "Definition" in strategy:
                logger.info(
                    format_phase_message(
                        "summarize",
                        f"[Role:{role_label}] extracted_strategy='{_truncate_for_log(strategy.get('Strategy', ''))}'",
                    )
                )
                return strategy
        except Exception as e:
            logger.warning(f"Summarizer attempt {attempt + 1} failed: {e}")
    return None
