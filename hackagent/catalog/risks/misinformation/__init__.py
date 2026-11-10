# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The Misinformation risk.

Tests whether the LLM produces factual fabrications, invented sources, or
misrepresented expertise. Exports the ``MisinformationType`` sub-types, the
``Misinformation`` vulnerability and the ``MISINFORMATION_PROFILE`` threat
profile.
"""

from hackagent.catalog.risks.misinformation.types import MisinformationType
from hackagent.catalog.risks.misinformation.vulnerabilities import Misinformation
from hackagent.catalog.risks.misinformation.profile import MISINFORMATION_PROFILE

__all__ = ["MisinformationType", "Misinformation", "MISINFORMATION_PROFILE"]
