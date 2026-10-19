# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Targets for live-browser chatbots."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse


def build_web_target(
    url: str,
    *,
    name: Optional[str] = None,
    headless: bool = True,
    input_selector: Optional[str] = None,
    reply_selector: Optional[str] = None,
    launcher_selector: Optional[str] = None,
    dismiss_consent: bool = True,
    llm_fallback_model: Optional[str] = None,
    timeout: Optional[int] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Build the ``("web", operational_config)`` target for a live-browser chatbot."""
    config: Dict[str, Any] = {
        "name": name or urlparse(url).netloc or url,
        "url": url,
        "endpoint": url,
        "headless": headless,
    }
    if input_selector:
        config["input_selector"] = input_selector
    if reply_selector:
        config["reply_selector"] = reply_selector
    if launcher_selector:
        config["launcher_selector"] = launcher_selector
    if not dismiss_consent:
        config["dismiss_consent"] = False
    if llm_fallback_model:
        config["llm_fallback_model"] = llm_fallback_model
    if timeout is not None:
        config["timeout"] = timeout
    return "web", config


__all__ = ["build_web_target"]
