# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Jailbreak framing for the RAG poisoning pipeline.

Reuses existing jailbreak techniques (static templates, h4rm3l decorator
programs, and others) to reframe the attacker goal before the poisoner LLM
turns it into a document payload. The reframed goal is what gets embedded in
poisoned documents; judging still uses the original goal.
"""

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from hackagent.attacks.generator import AttackTemplates
from hackagent.attacks.techniques.cipherchat.encode_experts import encode_expert_dict
from hackagent.attacks.techniques.h4rm3l.config import PRESET_PROGRAMS
from hackagent.attacks.techniques.h4rm3l.decorators import (
    compile_program,
    program_uses_llm_assisted_decorators,
)
from hackagent.router.router import AgentRouter

SUPPORTED_JAILBREAK_TECHNIQUES = (
    "static_template",
    "h4rm3l",
    "flipattack",
    "cipherchat",
)

DEFAULT_JAILBREAK_CONFIG: Dict[str, Any] = {
    "enabled": False,
    "technique": "static_template",
    # static_template options
    "template_categories": ["role_play"],
    # h4rm3l options
    "program": "refusal_suppression",
    "syntax_version": 2,
    # flipattack options
    "flip_mode": "FCS",
    # cipherchat options
    "encode_method": "caesar",
}


class JailbreakFramer:
    """Applies a jailbreak transformation to a goal string.

    Args:
        technique: Name of the jailbreak technique used.
        transform: Callable ``(goal, variant_index) -> (framed_goal, details)``.
    """

    def __init__(
        self,
        technique: str,
        transform: Callable[[str, int], Tuple[str, Dict[str, Any]]],
    ):
        self.technique = technique
        self._transform = transform

    def apply(self, goal: str, variant_index: int = 0) -> Tuple[str, Dict[str, Any]]:
        """Return the jailbreak-framed goal and its metadata."""
        framed, details = self._transform(goal, variant_index)
        metadata = {"technique": self.technique, **details}
        return framed, metadata


def _collect_static_templates(categories: List[str]) -> List[Tuple[str, str]]:
    """Return ``(category, template)`` pairs usable with a plain ``{goal}``."""
    templates: List[Tuple[str, str]] = []
    for category in categories:
        for template in AttackTemplates.get_by_category(str(category)):
            if "{goal}" in template:
                templates.append((str(category), template))
    return templates


def _build_static_template_framer(
    config: Dict[str, Any],
    logger: Optional[logging.Logger] = None,
    attacker_router: Optional[AgentRouter] = None,
    attacker_reg_key: Optional[str] = None,
) -> JailbreakFramer:
    raw_categories = config.get("template_categories") or ["role_play"]
    if isinstance(raw_categories, str):
        raw_categories = [raw_categories]
    categories = [str(c) for c in raw_categories]

    templates = _collect_static_templates(categories)
    if not templates:
        raise ValueError(
            "No usable static jailbreak templates found for categories "
            f"{categories}. Available categories: "
            f"{AttackTemplates.get_all_categories()}"
        )

    def _transform(goal: str, variant_index: int) -> Tuple[str, Dict[str, Any]]:
        category, template = templates[variant_index % len(templates)]
        return (
            AttackTemplates.apply_template(template, goal),
            {"template_category": category, "template": template},
        )

    return JailbreakFramer("static_template", _transform)


def _build_h4rm3l_framer(
    config: Dict[str, Any],
    logger: Optional[logging.Logger] = None,
    attacker_router: Optional[AgentRouter] = None,
    attacker_reg_key: Optional[str] = None,
) -> JailbreakFramer:
    program_name = str(config.get("program", "refusal_suppression"))
    program = PRESET_PROGRAMS.get(program_name, program_name)

    raw_syntax_version = config.get("syntax_version", 2)
    try:
        syntax_version = int(raw_syntax_version)
    except (TypeError, ValueError):
        syntax_version = 2

    if program_uses_llm_assisted_decorators(program, syntax_version):
        raise ValueError(
            f"h4rm3l program '{program_name}' uses LLM-assisted decorators, which "
            "are not supported inside the RAG poisoning pipeline. Choose a "
            "purely syntactic program instead."
        )

    decorate = compile_program(program, syntax_version)

    def _transform(goal: str, variant_index: int) -> Tuple[str, Dict[str, Any]]:
        return decorate(goal), {"program": program_name}

    return JailbreakFramer("h4rm3l", _transform)


def _flip_word_order(text: str) -> str:
    return " ".join(text.split()[::-1])


def _flip_char_in_word(text: str) -> str:
    return " ".join(word[::-1] for word in text.split())


def _flip_char_in_sentence(text: str) -> str:
    return text[::-1]


_FLIPATTACK_MODES: Dict[str, Callable[[str], str]] = {
    "FWO": _flip_word_order,
    "FCW": _flip_char_in_word,
    "FCS": _flip_char_in_sentence,
}


def _build_flipattack_framer(
    config: Dict[str, Any],
    logger: Optional[logging.Logger] = None,
    attacker_router: Optional[AgentRouter] = None,
    attacker_reg_key: Optional[str] = None,
) -> JailbreakFramer:
    raw_modes = config.get("flip_modes") or [config.get("flip_mode", "FCS")]
    if isinstance(raw_modes, str):
        raw_modes = [raw_modes]
    modes = [str(m).strip().upper() for m in raw_modes]
    for mode in modes:
        if mode not in _FLIPATTACK_MODES:
            raise ValueError(
                f"Unsupported flipattack flip_mode '{mode}'. "
                f"Supported: {sorted(_FLIPATTACK_MODES)}"
            )

    def _transform(goal: str, variant_index: int) -> Tuple[str, Dict[str, Any]]:
        mode = modes[variant_index % len(modes)]
        return _FLIPATTACK_MODES[mode](goal), {"flip_mode": mode}

    return JailbreakFramer("flipattack", _transform)


def _build_cipherchat_framer(
    config: Dict[str, Any],
    logger: Optional[logging.Logger] = None,
    attacker_router: Optional[AgentRouter] = None,
    attacker_reg_key: Optional[str] = None,
) -> JailbreakFramer:
    raw_methods = config.get("encode_methods") or [
        config.get("encode_method", "caesar")
    ]
    if isinstance(raw_methods, str):
        raw_methods = [raw_methods]
    methods = [str(m).strip().lower() for m in raw_methods]
    for method in methods:
        if method not in encode_expert_dict:
            raise ValueError(
                f"Unsupported cipherchat encode_method '{method}'. "
                f"Supported: {sorted(encode_expert_dict)}"
            )

    def _transform(goal: str, variant_index: int) -> Tuple[str, Dict[str, Any]]:
        method = methods[variant_index % len(methods)]
        return encode_expert_dict[method].encode(goal), {"encode_method": method}

    return JailbreakFramer("cipherchat", _transform)


_TECHNIQUE_BUILDERS: Dict[str, Callable[..., JailbreakFramer]] = {
    "static_template": _build_static_template_framer,
    "h4rm3l": _build_h4rm3l_framer,
    "flipattack": _build_flipattack_framer,
    "cipherchat": _build_cipherchat_framer,
}


def build_jailbreak_framer(
    config: Optional[Dict[str, Any]],
    logger: logging.Logger,
    attacker_router: Optional[AgentRouter] = None,
    attacker_reg_key: Optional[str] = None,
) -> Optional[JailbreakFramer]:
    """Build a :class:`JailbreakFramer` from a ``poisoning.jailbreak`` config.

    Returns ``None`` when jailbreak framing is disabled or unconfigured.

    Args:
        config: The ``poisoning.jailbreak`` config dict.
        logger: Logger for status/warning messages.
        attacker_router: Attacker LLM router, required by LLM-assisted
            techniques (``pap``, ``fc``). Ignored by purely syntactic ones.
        attacker_reg_key: Registration key for ``attacker_router``.

    Raises:
        ValueError: If the configuration requests an unsupported technique,
            an unusable template/program, or an LLM-assisted technique
            without an attacker router.
    """
    if not isinstance(config, dict) or not config.get("enabled", False):
        return None

    technique = str(config.get("technique", "static_template")).strip().lower()
    builder = _TECHNIQUE_BUILDERS.get(technique)
    if builder is None:
        raise ValueError(
            f"Unsupported jailbreak technique '{technique}'. "
            f"Supported: {list(SUPPORTED_JAILBREAK_TECHNIQUES)}"
        )

    framer = builder(config, logger, attacker_router, attacker_reg_key)

    logger.info(f"Jailbreak framing enabled for RAG poisoning: {technique}")
    return framer
