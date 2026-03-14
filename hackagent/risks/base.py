# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Base vulnerability class for all hackagent risk assessments.

Architecture (mirrors the attack layer):
    HackAgent.hack() → AttackOrchestrator → BaseAttack (technique)
                                              ↕
                     BaseVulnerability ← vulnerability.assess()

Each concrete vulnerability:
  1. Defines an Enum of sub-types in its ``types.py``
  2. Provides prompt templates in its ``templates.py``
  3. Extends this class in its main module (e.g. ``bias.py``)
"""

import abc
from hackagent.logger import get_logger
from enum import Enum
from typing import Any, Dict, List, Optional, Type

logger = get_logger(__name__)


class BaseVulnerability(abc.ABC):
    """
    Abstract base class for all vulnerabilities.

    Each vulnerability carries an ``Enum`` of sub-types that can be individually selected.

    Subclasses must set the class-level attributes:
        - ``name``             – human-readable name
        - ``description``      – one-liner for reports
        - ``ALLOWED_TYPES``    – list of valid sub-type *values* (strings)
        - ``_type_enum``       – the Enum class used for validation

    Parameters
    ----------
    types : list[Enum]
        Sub-types to evaluate (defaults to all allowed types).
    """

    # ── Class-level attributes (set by each concrete vulnerability) ──
    name: str = ""
    description: str = ""
    ALLOWED_TYPES: List[str] = []
    _type_enum: Optional[Type[Enum]] = None

    def __init__(self, types: Optional[List[Enum]] = None):
        if types is None and self._type_enum is not None:
            types = list(self._type_enum)
        self.types: List[Enum] = types or []

    # ── Helpers ──────────────────────────────────────────────────────

    def get_types(self) -> List[Enum]:
        """Return the list of selected sub-type enums."""
        return self.types

    def get_values(self) -> List[str]:
        """Return selected sub-type values as plain strings."""
        return [t.value for t in self.types]

    def get_name(self) -> str:
        return self.name

    # ── Assess / simulate stubs (overridden by concrete classes) ─────

    def assess(
        self,
        model_callback: Any = None,
        purpose: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate the target model for this vulnerability.

        Returns a dict mapping each sub-type value to its test-case results.
        """
        raise NotImplementedError

    async def a_assess(
        self,
        model_callback: Any = None,
        purpose: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Async variant of :pymeth:`assess`."""
        raise NotImplementedError

    def simulate_attacks(self, purpose: Optional[str] = None) -> List[str]:
        """
        Generate baseline attack prompts for each selected sub-type.

        Returns a flat list of attack strings.
        """
        raise NotImplementedError

    async def a_simulate_attacks(self, purpose: Optional[str] = None) -> List[str]:
        """Async variant of :pymeth:`simulate_attacks`."""
        raise NotImplementedError

    # ── Display ──────────────────────────────────────────────────────

    def __repr__(self) -> str:
        type_vals = ", ".join(self.get_values())
        return f"{self.__class__.__name__}(types=[{type_vals}])"
