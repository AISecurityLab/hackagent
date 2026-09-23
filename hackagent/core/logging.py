# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Logger access for library code.

Library modules only obtain loggers; they never install handlers or set
levels. Handler configuration belongs to the application (the CLI does it in
:mod:`hackagent.cli.logging_setup`).
"""

import logging


def get_logger(name: str) -> logging.Logger:
    """Return the logger called ``name`` without configuring it."""
    return logging.getLogger(name)
