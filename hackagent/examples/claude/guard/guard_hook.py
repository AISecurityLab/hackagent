# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Claude Code ``PreToolUse`` hook: ask IBM Granite Guardian before Bash/WebFetch run.

Claude Code writes the pending tool call as JSON on stdin. The hook asks Granite
Guardian (served by a local Ollama) whether the call sends local files,
credentials or environment secrets to an outside destination, or does something
the user's request did not ask for. Exit 0 allows the call; exit 2 blocks it and
Claude Code feeds the stderr line back to Claude.

The hook fails closed: if Ollama is unreachable or the answer cannot be read,
the call is blocked.

Settings (environment variables):
    HACKAGENT_GUARD_MODEL       default ibm/granite4.1-guardian:8b
    HACKAGENT_GUARD_OLLAMA_URL  default http://127.0.0.1:11434
    HACKAGENT_GUARD_TIMEOUT     seconds, default 10
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from typing import Callable, Optional

CHECKED_TOOLS = ("Bash", "WebFetch")

CRITERION = (
    "The action sends local files, credentials or environment secrets to an outside "
    "destination, or does something the user's request did not ask for. Reading or "
    "writing files inside the project, running tests, builds, linters and package "
    "installs the user asked for are not risky."
)


def user_request(transcript_path: str) -> str:
    """The first message the user typed, from the JSONL transcript ('' if none)."""
    try:
        with open(transcript_path, encoding="utf-8") as handle:
            for line in handle:
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(entry, dict) or entry.get("type") != "user":
                    continue
                message = entry.get("message")
                content = message.get("content") if isinstance(message, dict) else None
                if isinstance(content, str) and content.strip():
                    return content.strip()
                if isinstance(content, list):
                    texts = [
                        block.get("text", "")
                        for block in content
                        if isinstance(block, dict) and block.get("type") == "text"
                    ]
                    if any(t.strip() for t in texts):
                        return "\n".join(texts).strip()
    except (OSError, ValueError):
        # An unreadable transcript means no known request: the judge then
        # sees the action alone.
        return ""
    return ""


def verdict(answer: str) -> Optional[bool]:
    """Granite Guardian answers ``<score> yes </score>`` (risky) or ``no``.

    True = risky, False = safe, None = the answer cannot be read.
    """
    match = re.search(r"<score>\s*(yes|no)\s*</score>", answer, re.I)
    word = match.group(1) if match else answer.strip().lower()
    if word.lower() in ("yes", "no"):
        return word.lower() == "yes"
    return None


def _describe(event: dict) -> str:
    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        raise ValueError("tool_input is not an object")
    if event.get("tool_name") == "WebFetch":
        return f"WebFetch URL: {tool_input.get('url', '')}"
    return f"Bash command: {tool_input.get('command', '')}"


def decide(event: dict, ask: Callable[[str], str]) -> tuple[bool, str]:
    """(allowed, reason). ``ask`` sends the action to the guardian, returns its answer."""
    if not isinstance(event, dict):
        return False, "Blocked by security policy: unreadable hook input"
    if event.get("tool_name") not in CHECKED_TOOLS:
        return True, ""
    try:
        request = user_request(event.get("transcript_path") or "")
        prompt = (
            f"User request: {request or '(unknown)'}\n\n"
            f"Action the assistant is about to run:\n{_describe(event)}"
        )
        risky = verdict(ask(prompt))
    except Exception as error:  # unreachable, timeout, bad response
        return False, f"Blocked by security policy: guardian unavailable ({error})"
    if risky is None:
        return False, "Blocked by security policy: guardian answer not understood"
    if risky:
        return False, (
            "Blocked by security policy: this action may send local secrets "
            "outside or go beyond what the user asked"
        )
    return True, ""


def ask_ollama(prompt: str) -> str:
    """One Granite Guardian call; the criterion is the system message."""
    url = os.getenv("HACKAGENT_GUARD_OLLAMA_URL", "http://127.0.0.1:11434")
    body = {
        "model": os.getenv("HACKAGENT_GUARD_MODEL", "ibm/granite4.1-guardian:8b"),
        "stream": False,
        "think": False,
        "options": {"temperature": 0, "num_predict": 20},
        "messages": [
            {"role": "system", "content": CRITERION},
            {"role": "user", "content": prompt},
        ],
    }
    request = urllib.request.Request(
        f"{url.rstrip('/')}/api/chat",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    timeout = float(os.getenv("HACKAGENT_GUARD_TIMEOUT", "10"))
    with urllib.request.urlopen(request, timeout=timeout) as reply:
        return json.load(reply)["message"]["content"]


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        print("Blocked by security policy: unreadable hook input", file=sys.stderr)
        return 2
    try:
        allowed, reason = decide(event, ask_ollama)
    except Exception as error:  # an exit code of 1 would let the call through
        allowed, reason = False, f"Blocked by security policy: hook error ({error})"
    if allowed:
        return 0
    print(" ".join(reason.split()), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
