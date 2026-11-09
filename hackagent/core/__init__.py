# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Foundation shared by every package: settings, defaults, errors, logging.

``core`` is the bottom layer: every other package may import it and it
imports none of them. :mod:`~hackagent.core.settings` resolves credentials
and locations, :mod:`~hackagent.core.credentials` handles ``${VARIABLE}``
API key references, and :mod:`~hackagent.core.contracts` holds the types
that cross package boundaries (messages, completions, verdicts, statuses).
"""
