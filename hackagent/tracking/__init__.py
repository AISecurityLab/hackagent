# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Shared helpers for recording a run's results.

The campaign runner owns its own tracking (``orchestrator.campaign.tracking``)
and uses only the submodules here directly:

- :mod:`~hackagent.tracking.evaluation`: ``eval_*`` result columns
- :mod:`~hackagent.tracking.serialize`: JSON-safe cleaning of trace content
"""
