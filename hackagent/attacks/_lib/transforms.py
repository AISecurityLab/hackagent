# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Shared utility functions for attacks.

This module provides common helper functions used across
objectives and techniques.
"""

import base64
import hashlib
import re
from typing import List


def deduplicate_by_content(items: List[str]) -> List[str]:
    """
    Remove duplicate strings while preserving order.

    Args:
        items: List of strings

    Returns:
        Deduplicated list
    """
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def deduplicate_by_hash(items: List[str], hash_length: int = 8) -> List[str]:
    """
    Remove near-duplicates using content hashing.

    Args:
        items: List of strings
        hash_length: Number of hash characters to compare

    Returns:
        Deduplicated list
    """
    seen_hashes = set()
    result = []

    for item in items:
        content_hash = hashlib.md5(item.encode()).hexdigest()[:hash_length]
        if content_hash not in seen_hashes:
            seen_hashes.add(content_hash)
            result.append(item)

    return result


def encode_base64(text: str) -> str:
    """Encode text to base64."""
    return base64.b64encode(text.encode()).decode()


def decode_base64(text: str) -> str:
    """Decode base64 text."""
    try:
        return base64.b64decode(text.encode()).decode()
    except Exception:
        return text


def simple_obfuscate(text: str) -> str:
    """
    Simple text obfuscation (leetspeak-style).

    Args:
        text: Text to obfuscate

    Returns:
        Obfuscated text
    """
    replacements = {
        "a": "4",
        "e": "3",
        "i": "1",
        "o": "0",
        "A": "4",
        "E": "3",
        "I": "1",
        "O": "0",
    }

    result = text
    for old, new in replacements.items():
        result = result.replace(old, new)

    return result


def split_into_chunks(text: str, chunk_size: int = 100) -> List[str]:
    """
    Split text into chunks of specified size.

    Args:
        text: Text to split
        chunk_size: Maximum chunk size

    Returns:
        List of text chunks
    """
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace in text.

    Args:
        text: Text to normalize

    Returns:
        Text with normalized whitespace
    """
    # Replace multiple spaces with single space
    text = re.sub(r"\s+", " ", text)
    # Strip leading/trailing whitespace
    return text.strip()


def truncate_text(text: str, max_length: int = 1000, suffix: str = "...") -> str:
    """
    Truncate text to maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add when truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[: max_length - len(suffix)] + suffix
