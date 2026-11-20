# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Indirect-injection techniques.

The payload reaches the target through content it retrieves or a tool
returns, not through the user turn: rag (poisoned retrieval documents),
tool_output_ipi (poisoned tool output), toolhijacker (poisoned tool
registry descriptions) and repo_injection (a poisoned file in the repository
a coding agent works on). Their primary category in
:mod:`hackagent.catalog.taxonomy` is still static or adaptive; the
``indirect`` tag decides the folder, as it does in the docs.

Importing this package does not import the techniques in it.
"""
