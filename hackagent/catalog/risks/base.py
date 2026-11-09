# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Base class of the vulnerabilities in the risk catalog.

Each risk package under :mod:`hackagent.catalog.risks` defines an Enum of
sub-types (``types.py``), a :class:`BaseVulnerability` subclass that names
and describes the risk (``vulnerabilities.py``) and a threat profile
(``profile.py``) that maps it to datasets, attacks and metrics. The classes
are reference data for planning and the docs: campaigns do not call the
``assess`` / ``simulate_attacks`` hooks, and no built-in vulnerability
implements them.
"""

import abc
from hackagent.core.logging import get_logger
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

    Args:
        types: Sub-types to evaluate. Defaults to every member of
            ``_type_enum``.
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
        """Return the vulnerability's human-readable name."""
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
        """Async variant of :meth:`assess`."""
        raise NotImplementedError

    def simulate_attacks(self, purpose: Optional[str] = None) -> List[str]:
        """
        Generate baseline attack prompts for each selected sub-type.

        Returns a flat list of attack strings.
        """
        raise NotImplementedError

    async def a_simulate_attacks(self, purpose: Optional[str] = None) -> List[str]:
        """Async variant of :meth:`simulate_attacks`."""
        raise NotImplementedError

    # ── Display ──────────────────────────────────────────────────────

    def __repr__(self) -> str:
        type_vals = ", ".join(self.get_values())
        return f"{self.__class__.__name__}(types=[{type_vals}])"
