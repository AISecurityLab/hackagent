# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Indirect-injection techniques.

The payload reaches the target through content it retrieves or a tool
returns, not through the user turn: rag (poisoned retrieval documents) and
tool_output_ipi (poisoned tool output). Their primary category in
:mod:`hackagent.catalog.taxonomy` is still static or adaptive; the
``indirect`` tag decides the folder, as it does in the docs.

Importing this package does not import the techniques in it.
"""
