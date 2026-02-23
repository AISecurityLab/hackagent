# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Utility helpers for the risks package.
"""

from enum import Enum
from typing import List, Type


def validate_vulnerability_types(
    vulnerability_name: str,
    types: List[str],
    allowed_type: Type[Enum],
) -> List[Enum]:
    """
    Validate and convert a list of string type values into Enum members.

    Raises ``ValueError`` if any string is not a valid member of the Enum.
    """
    validated = []
    for t in types:
        try:
            validated.append(allowed_type(t))
        except ValueError:
            allowed = [e.value for e in allowed_type]
            raise ValueError(
                f"Invalid type '{t}' for {vulnerability_name}. Allowed types: {allowed}"
            )
    return validated
