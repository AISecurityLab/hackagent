# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The Jailbreak risk.

Tests whether the LLM can be manipulated into bypassing its safety filters
through roleplay, encoding, multi-turn, hypothetical, or authority-manipulation
techniques. Exports the ``JailbreakType`` sub-types, the ``Jailbreak``
vulnerability and the ``JAILBREAK_PROFILE`` threat profile.
"""

from hackagent.catalog.risks.jailbreak.types import JailbreakType
from hackagent.catalog.risks.jailbreak.vulnerabilities import Jailbreak
from hackagent.catalog.risks.jailbreak.profile import JAILBREAK_PROFILE

__all__ = ["JailbreakType", "Jailbreak", "JAILBREAK_PROFILE"]
