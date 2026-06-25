# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Cached translation of attack system prompts into the goal's language.

When a goal is written in a non-English language, the attacker/judge system
prompts are translated into that language so the attack operates natively
(rather than steering an English prompt at, say, an Italian chatbot). Results
are cached per ``(prompt, language)`` so a batch of same-language goals — and
every iteration within a goal — translates each prompt at most once.

The caller supplies a ``complete(prompt) -> str`` callable (an LLM completion),
so this module is provider-agnostic and unit-testable without a live model.
Translation is always best-effort: any failure falls back to the original
English text so the attack never breaks.
"""

import hashlib
import re
from typing import Callable, Dict, Tuple

from hackagent.logger import get_logger

logger = get_logger(__name__)

# (sha256(text), language_lower) -> translated text.
_TRANSLATION_CACHE: Dict[Tuple[str, str], str] = {}
# sha256(goal) -> detected language name (English word, e.g. "Italian").
_LANGUAGE_CACHE: Dict[str, str] = {}

# Common language names, matched against the detector's reply so a preamble
# like "The language is Italian." still resolves correctly.
_KNOWN_LANGUAGES = (
    "english",
    "italian",
    "spanish",
    "french",
    "german",
    "portuguese",
    "dutch",
    "russian",
    "chinese",
    "japanese",
    "korean",
    "arabic",
    "hindi",
    "turkish",
    "polish",
    "swedish",
    "norwegian",
    "danish",
    "finnish",
    "greek",
    "romanian",
    "czech",
    "hungarian",
    "ukrainian",
    "hebrew",
    "thai",
    "vietnamese",
    "indonesian",
    "catalan",
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def clear_cache() -> None:
    """Clear the translation/language caches (mainly for tests)."""
    _TRANSLATION_CACHE.clear()
    _LANGUAGE_CACHE.clear()


def detect_language(goal: str, complete: Callable[[str], str]) -> str:
    """Return the English name of ``goal``'s language (cached). '' on failure."""
    goal = (goal or "").strip()
    if not goal:
        return ""
    key = _sha(goal)
    if key in _LANGUAGE_CACHE:
        return _LANGUAGE_CACHE[key]
    prompt = (
        "Identify the natural language of the text below. Reply with ONLY the "
        "English name of the language (for example: English, Italian, Spanish, "
        "French, German), nothing else.\n\nText:\n" + goal
    )
    try:
        raw = (complete(prompt) or "").strip()
    except Exception as exc:
        logger.debug("language detection failed: %s", exc)
        raw = ""
    lang = ""
    lowered = raw.lower()
    # Prefer a known language name anywhere in the reply (handles preamble like
    # "The language is Italian."); otherwise fall back to the first word.
    for known in _KNOWN_LANGUAGES:
        if re.search(rf"\b{known}\b", lowered):
            lang = known.capitalize()
            break
    if not lang:
        match = re.search(r"[A-Za-z]+", raw)
        lang = match.group(0).capitalize() if match else ""
    _LANGUAGE_CACHE[key] = lang
    return lang


def localize_text(text: str, goal: str, complete: Callable[[str], str]) -> str:
    """Translate ``text`` into ``goal``'s language (cached); English/failure → ``text``.

    ``text`` is the already-formatted system prompt (goal substituted), so there
    are no template placeholders to protect. JSON *keys* the attacker must emit
    verbatim (``improvement``/``prompt``) are explicitly kept in English.
    """
    lang = detect_language(goal, complete)
    if not lang or lang.lower().startswith("english"):
        return text

    key = (_sha(text), lang.lower())
    cached = _TRANSLATION_CACHE.get(key)
    if cached is not None:
        return cached

    prompt = (
        f"Translate the following text into {lang}. Keep it faithful and natural. "
        "Preserve ALL formatting exactly: JSON structure, braces, quotes, and "
        "line breaks. Do NOT translate JSON field names or keys such as "
        '"improvement" and "prompt" — keep those exact English words. Output '
        "ONLY the translated text, with no preamble or explanation.\n\nTEXT:\n" + text
    )
    try:
        translated = (complete(prompt) or "").strip()
    except Exception as exc:
        logger.warning("prompt translation to %s failed: %s", lang, exc)
        translated = ""

    if not translated:
        logger.warning("empty translation to %s; using original text.", lang)
        translated = text

    _TRANSLATION_CACHE[key] = translated
    return translated
