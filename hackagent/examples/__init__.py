# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""The example campaigns shipped with HackAgent, and how to find them.

Each example is a campaign file beside the thing it attacks. They are found
by looking rather than listed anywhere, so an example added to this tree is
one the CLI lists and the builder offers, with nothing to register.

This lives here rather than in an interface because both of them need it,
and because the examples are the ones that know where they are.
"""

from __future__ import annotations

from pathlib import Path

#: The folder this module is in, which is the one holding the examples.
EXAMPLES_DIR = Path(__file__).resolve().parent


def campaign_files() -> dict[str, Path]:
    """Every example campaign, keyed by ``folder/name``."""
    return {
        path.relative_to(EXAMPLES_DIR).with_suffix("").as_posix(): path
        for path in sorted(EXAMPLES_DIR.rglob("*.yaml"))
    }


def describe(campaign_path: Path) -> str:
    """The campaign's own one-line description, or ``""`` if it has none."""
    import yaml

    try:
        document = yaml.safe_load(campaign_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return ""
    campaign = document.get("campaign")
    return str(campaign.get("description") or "") if isinstance(campaign, dict) else ""


def resolve(name: str) -> tuple[str, Path]:
    """Match ``name`` against the examples, in full or by its last part.

    Raises :class:`LookupError` with a message worth showing when the name
    matches nothing, or more than one thing.
    """
    found = campaign_files()
    if name in found:
        return name, found[name]
    matches = sorted(key for key in found if key.rsplit("/", 1)[-1] == name)
    if len(matches) == 1:
        return matches[0], found[matches[0]]
    if matches:
        raise LookupError(f"'{name}' matches several examples: {', '.join(matches)}")
    raise LookupError(f"No example named '{name}'.")


__all__ = ["EXAMPLES_DIR", "campaign_files", "describe", "resolve"]
