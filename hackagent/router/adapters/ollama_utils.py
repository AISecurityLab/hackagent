# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Utility functions for Ollama model management.

This module provides common utilities for checking and pulling Ollama models
that can be shared across the codebase.
"""

import logging
import shutil
import subprocess
from typing import Optional, Set
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import urlopen

logger = logging.getLogger(__name__)


def is_ollama_available() -> bool:
    """Check if Ollama is installed and available in PATH."""
    return shutil.which("ollama") is not None


def is_ollama_running(endpoint: str = "http://localhost:11434") -> bool:
    """
    Check if Ollama server is running at the specified endpoint.

    Args:
        endpoint: Ollama API base URL

    Returns:
        True if Ollama is running and accessible
    """
    base = endpoint.rstrip("/")
    health_url = urljoin(base, "api/tags")

    try:
        with urlopen(health_url, timeout=3):
            return True
    except (URLError, TimeoutError, ValueError):
        return False


def get_installed_ollama_models() -> Set[str]:
    """
    Get list of models currently available in local Ollama.

    Returns:
        Set of installed model names

    Raises:
        RuntimeError: If Ollama is not installed or model listing fails
    """
    if not is_ollama_available():
        raise RuntimeError("Ollama is not installed or not in PATH")

    result = subprocess.run(
        ["ollama", "list"],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        stderr = result.stderr.strip() or "unknown error"
        raise RuntimeError(f"Failed to read local Ollama models: {stderr}")

    models: Set[str] = set()
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    # Skip header line
    for line in lines[1:]:
        model_name = line.split()[0]
        if model_name:
            models.add(model_name)
    return models


def normalize_ollama_model_aliases(model_name: str) -> Set[str]:
    """
    Return equivalent model aliases considering Ollama's implicit :latest tag.

    Args:
        model_name: Model name to normalize

    Returns:
        Set of equivalent model name aliases
    """
    aliases = {model_name}
    if ":" in model_name:
        base, tag = model_name.rsplit(":", 1)
        if tag == "latest":
            aliases.add(base)
    else:
        aliases.add(f"{model_name}:latest")
    return aliases


def is_model_installed(
    model_name: str, installed_models: Optional[Set[str]] = None
) -> bool:
    """
    Check if a model is installed locally, accounting for equivalent :latest aliases.

    Args:
        model_name: Model name to check
        installed_models: Optional set of installed models. If None, will be fetched.

    Returns:
        True if model is installed
    """
    if installed_models is None:
        try:
            installed_models = get_installed_ollama_models()
        except RuntimeError:
            return False

    aliases = normalize_ollama_model_aliases(model_name)
    return any(alias in installed_models for alias in aliases)


def pull_ollama_model(model_name: str) -> bool:
    """
    Pull an Ollama model if it's not already installed.

    Args:
        model_name: Model name to pull

    Returns:
        True if model was pulled successfully or already installed, False otherwise
    """
    # Check if Ollama is available
    if not is_ollama_available():
        logger.warning("Ollama is not installed or not in PATH")
        return False

    # Check if already installed
    try:
        if is_model_installed(model_name):
            logger.info(f"Ollama model '{model_name}' is already installed")
            return True
    except RuntimeError as e:
        logger.warning(f"Failed to check installed models: {e}")
        # Continue to attempt pull anyway

    # Attempt to pull the model
    logger.info(f"Pulling Ollama model '{model_name}'...")
    try:
        pull_result = subprocess.run(
            ["ollama", "run", model_name, "ping"],
            capture_output=True,
            text=True,
            check=False,
            timeout=300,  # 5 minute timeout for large models
        )

        if pull_result.returncode != 0:
            stderr = pull_result.stderr.strip() or "unknown error"
            logger.error(f"Failed to pull Ollama model '{model_name}': {stderr}")
            return False

        logger.info(f"Successfully pulled Ollama model '{model_name}'")
        return True

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout while pulling Ollama model '{model_name}'")
        return False
    except Exception as e:
        logger.error(f"Unexpected error pulling Ollama model '{model_name}': {e}")
        return False


__all__ = [
    "is_ollama_available",
    "is_ollama_running",
    "get_installed_ollama_models",
    "normalize_ollama_model_aliases",
    "is_model_installed",
    "pull_ollama_model",
]
