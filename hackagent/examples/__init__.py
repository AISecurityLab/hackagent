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

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

#: The folder this module is in, which is the one holding the examples.
EXAMPLES_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Target:
    """A server an example attacks, which ``hackagent examples run`` can
    start for you."""

    script: str
    port: int
    label: str


#: Examples whose target is a local server, by the folder holding the campaign.
TARGETS: dict[str, Target] = {
    "openai_sdk/pc_tool_sandbox": Target("agent.py", 5001, "PC Tool agent"),
    "openai_sdk/db_tool_sandbox": Target("agent.py", 5002, "DB Tool agent"),
    "openai_sdk/rag": Target("agent_server.py", 8000, "Corporate policy RAG agent"),
    "langchain/rag": Target("agent_server.py", 8000, "LangChain RAG agent"),
}

#: Examples whose target is not started for you, and what to run instead.
MANUAL_TARGETS: dict[str, str] = {
    "google_adk/jailbreak_eval": (
        "cd hackagent/examples/google_adk && adk api_server --port 8000 ."
    ),
    "google_adk/multi_tool_agent": (
        "cd hackagent/examples/google_adk && adk api_server --port 8000 ."
    ),
}


def needs(name: str) -> str:
    """What the example ``name`` needs running besides HackAgent, in a few
    words: ``starts agent.py``, ``needs adk api_server``, or ``""``."""
    folder = name.rsplit("/", 1)[0] if "/" in name else ""
    target: Optional[Target] = TARGETS.get(folder)
    if target is not None:
        return f"starts {target.script}"
    if folder in MANUAL_TARGETS:
        return "needs adk api_server"
    return ""


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


__all__ = [
    "EXAMPLES_DIR",
    "MANUAL_TARGETS",
    "TARGETS",
    "Target",
    "campaign_files",
    "describe",
    "needs",
    "resolve",
]
