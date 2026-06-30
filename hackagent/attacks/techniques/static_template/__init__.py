# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Static template attack technique.

Uses predefined prompt templates combined with harmful goals to attempt
jailbreaks. Simpler than optimization-based approaches like AdvPrefix,
but can be effective for testing basic prompt injection vulnerabilities.

Architecture:
- generation.py: Generate and execute static template prompts
- evaluation.py: Evaluate responses using objective-based criteria
- attack.py: Main attack class coordinating the pipeline
- config.py: Configuration and defaults
"""

from .attack import StaticTemplateAttack

__all__ = ["StaticTemplateAttack"]
