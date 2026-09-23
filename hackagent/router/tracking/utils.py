# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Shared serialization utilities for the tracking subsystem.

Single source of truth for:
- deep_clean: converts Pydantic/OpenAI model objects to plain Python structures
- sanitize_for_json: unified JSON sanitization (inf/nan, sensitive keys,
  client objects, non-serializable fallback)

Both tracker.py and step.py import from here; any fix or improvement needs
to be made in exactly one place.
"""

import json
import math
from typing import Any

# Keys whose values should be replaced with a type placeholder (e.g. httpx clients)
_SKIP_KEYS: frozenset = frozenset({"_client", "client"})

# Substrings that mark a key as containing sensitive data
_SENSITIVE_SUBSTRINGS: tuple = ("key", "token", "secret", "password")

# Exact-match allowlist for legitimate numeric token-count metrics that contain
# the substring ``token`` but are not secrets. Only these keys are exempt from
# the sensitive-substring redaction; everything else with ``token`` stays
# redacted (e.g. ``api_token``, ``api_tokens``, ``secret_tokens``).
# ``reasoning_tokens`` is included because ``completion_tokens_details``
# may contain it as a numeric sub-field.
_TOKEN_COUNT_ALLOWLIST: frozenset = frozenset(
    {
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "input_tokens",
        "output_tokens",
        "cached_tokens",
        "token_count",
        "prompt_tokens_details",
        "completion_tokens_details",
        "reasoning_tokens",
    }
)


def deep_clean(obj: Any) -> Any:
    """
    Recursively convert Pydantic/OpenAI model objects to plain dicts/lists.

    Handles objects with ``model_dump()`` (Pydantic v2) or ``dict()``
    (Pydantic v1 / legacy), and recurses into dicts and lists.
    All other values are returned as-is.

    Args:
        obj: Any object to clean.

    Returns:
        A plain Python structure with no Pydantic model instances.
    """
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):  # legacy Pydantic v1
        return obj.dict()
    if isinstance(obj, dict):
        return {k: deep_clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [deep_clean(v) for v in obj]
    return obj


def sanitize_for_json(obj: Any) -> Any:
    """
    Unified JSON sanitization for tracking payloads.

    Applies the following rules recursively:

    - ``None`` → ``None``
    - ``dict``:
        - Keys in ``_SKIP_KEYS`` (``_client``, ``client``) → ``"<TypeName>"``
        - Keys whose lowercase form is in ``_TOKEN_COUNT_ALLOWLIST``
          (e.g. ``prompt_tokens``, ``total_tokens``, ``token_count``) are
          preserved — they contain ``token`` but are numeric usage metrics, not
          secrets. This allowlist is checked *before* the sensitive-substring
          test so only explicitly safe metric names are exempt.
        - Keys whose lowercase form contains a sensitive substring
          (``key``, ``token``, ``secret``, ``password``) → ``"***REDACTED***"``
          (including ``api_tokens``/``secret_tokens``/``password_tokens`` which
          are *not* in the allowlist)
        - All other values recurse.
    - ``list`` / ``tuple`` → recurse element-wise, preserving type.
    - ``float``: ``inf``/``-inf`` → ``"Infinity"``/``"-Infinity"``,
      ``nan`` → ``"NaN"``, finite float returned as-is.
    - ``str``, ``int``, ``bool`` → returned as-is.
    - Anything else: attempt ``json.dumps``; if that fails, return ``"<TypeName>"``.

    Args:
        obj: Any object to sanitize.

    Returns:
        A JSON-serializable Python structure.
    """
    if obj is None:
        return None

    if isinstance(obj, dict):
        sanitized: dict = {}
        for k, v in obj.items():
            if k in _SKIP_KEYS:
                sanitized[k] = f"<{type(v).__name__}>"
                continue
            # Preserve explicitly allowlisted numeric token-count metrics even
            # though they contain the substring ``token``. This runs before the
            # generic sensitive check so only the enumerated metric names are
            # exempt; ``api_tokens`` etc. remain redacted.
            if k.lower() in _TOKEN_COUNT_ALLOWLIST:
                sanitized[k] = sanitize_for_json(v)
                continue
            if any(s in k.lower() for s in _SENSITIVE_SUBSTRINGS):
                sanitized[k] = "***REDACTED***"
                continue
            sanitized[k] = sanitize_for_json(v)
        return sanitized

    if isinstance(obj, (list, tuple)):
        result = [sanitize_for_json(item) for item in obj]
        return tuple(result) if isinstance(obj, tuple) else result

    if isinstance(obj, float):
        if math.isinf(obj):
            return "Infinity" if obj > 0 else "-Infinity"
        if math.isnan(obj):
            return "NaN"
        return obj

    if isinstance(obj, (str, int, bool)):
        return obj

    # Fallback: attempt JSON serialization; replace non-serializable with type name.
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return f"<{type(obj).__name__}>"
