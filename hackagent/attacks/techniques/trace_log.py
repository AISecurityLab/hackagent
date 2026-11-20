# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Log each node an attack records, so a run can be followed as it happens.

Every :class:`~.trace.TraceNode` also becomes a record of the
:data:`~hackagent.core.logging.TRACE_LOGGER` logger. Which attack and goal
it belongs to comes from :func:`~.trace.about`, set by the campaign runner;
where it sits in the search, from the phases it is nested in. The record's
message is plain text, and its ``trace_step`` holds the same facts as fields
for a handler that draws them.

Levels say how much a reader wants:

- ``INFO``: what the search decided (stopped, pruned, skipped…), what it
  wrote down, and each panel verdict, as a score. No prompt or reply text:
  of the data a decision or artifact carries, only numbers, flags and a
  ``uri`` are shown (:func:`safe_details`); the rest stays in the trace.
- ``DEBUG``: every model call with a short snippet of what came back (the
  target's reply, the attacker's prompt…).

Phases are not logged on their own: every record names the phases it is
nested in, so a line that only opens one would say nothing new.
- ``WARNING``: a call that failed.

Nothing is computed unless the record's level is enabled.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping, Sequence
from typing import Any, Optional

from hackagent.core.logging import TRACE_LOGGER, goal_label

logger = logging.getLogger(TRACE_LOGGER)

#: Longest snippet of a call's text, and of a value in a decision's data.
SNIPPET_CHARS = 100
VALUE_CHARS = 60

_SPACE = re.compile(r"\s+")


def level_of(node: Any) -> Optional[int]:
    """The level a node is logged at, or None for one not logged (a phase)."""
    if node.node == "phase":
        return None
    if node.error:
        return logging.WARNING
    if node.node in ("decision", "artifact"):
        return logging.INFO
    if node.node == "call" and node.label == "panel":
        return logging.INFO
    return logging.DEBUG


def snippet(value: Any, limit: int = SNIPPET_CHARS) -> str:
    """``value`` as one short line of text."""
    if value is None:
        return ""
    if isinstance(value, Sequence) and not isinstance(value, str):
        # A chat request: what was last said.
        value = next(
            (
                item.get("content")
                for item in reversed(value)
                if isinstance(item, Mapping) and item.get("content")
            ),
            "",
        )
    if isinstance(value, Mapping):
        value = value.get("response") or value.get("prompt") or ""
    if isinstance(value, list):
        value = " ".join(
            str(part.get("text", "")) for part in value if isinstance(part, Mapping)
        )
    text = _SPACE.sub(" ", str(value)).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


#: Fields an attacker's JSON reply puts its proposal in, most specific first.
_PROPOSAL_KEYS = ("prompt", "adversarial_prompt", "question", "response")


def proposal(value: Any) -> Any:
    """What an attacker proposed: the ``prompt`` of a JSON reply such as
    PAIR's ``{"improvement": ..., "prompt": ...}``, else the reply itself."""
    if not isinstance(value, str):
        return value
    text = value.strip()
    start = text.find("{")
    if start < 0:
        return value
    try:
        data, _ = json.JSONDecoder().raw_decode(text[start:])
    except ValueError:
        return value
    if isinstance(data, Mapping):
        for key in _PROPOSAL_KEYS:
            if isinstance(data.get(key), str) and data[key].strip():
                return data[key]
    return value


def _value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:g}"
    return snippet(value, VALUE_CHARS)


#: Keys whose text names where something is, never what it says.
_SAFE_TEXT_KEYS = frozenset({"uri"})


def safe_details(data: Mapping[str, Any], skip: str = "") -> dict[str, str]:
    """The data of a decision or artifact a log may show: numbers, flags and
    locations. Text, lists and mappings can hold attack text (a program, a
    poisoned document, a tool description) and are left to the trace."""
    return {
        key: _value(value)
        for key, value in data.items()
        if key != skip
        and (
            isinstance(value, (bool, int, float))
            or (key in _SAFE_TEXT_KEYS and isinstance(value, str))
        )
    }


def _usage(data: Mapping[str, Any]) -> Optional[int]:
    usage = data.get("usage")
    if not isinstance(usage, Mapping):
        return None
    tokens = [usage.get(key) for key in ("prompt_tokens", "completion_tokens")]
    numbers = [value for value in tokens if isinstance(value, int)]
    return sum(numbers) if numbers else None


def describe(
    node: Any,
    subject: Mapping[str, Any],
    within: Sequence[str],
    label: Optional[str] = None,
) -> dict[str, Any]:
    """The fields of a node's record: who, where, what, and its message.

    ``label`` is the phase's label as the log shows it (numbered)."""
    data = node.data if isinstance(node.data, Mapping) else {}
    step: dict[str, Any] = {
        "attack": subject.get("attack"),
        "goal": subject.get("goal"),
        "scope": node.scope,
        "path": list(node.path),
        "depth": len(node.path),
        "node": node.node,
        "label": label or node.label,
        "within": list(within),
        "latency_s": node.latency_s,
        "error": node.error,
    }
    if node.node == "decision":
        step["reason"] = str(data.get("reason") or "")
        step["details"] = safe_details(data, skip="reason")
        body = node.label + (f": {step['reason']}" if step["reason"] else "")
        if step["details"]:
            body += (
                " (" + ", ".join(f"{k}={v}" for k, v in step["details"].items()) + ")"
            )
    elif node.node == "artifact":
        step["details"] = safe_details(data)
        body = f"artifact {node.label}" + (
            f" {step['details']['uri']}" if step["details"].get("uri") else ""
        )
    elif node.node == "phase":
        step["details"] = safe_details(data)
        body = step["label"]
    elif node.node == "call":
        step["role"] = node.label
        step["tokens"] = _usage(data)
        response = data.get("response")
        if node.label == "panel" and isinstance(response, Mapping):
            step["score"] = response.get("score")
            step["success"] = response.get("success")
            # The dashboard's words: jailbroken or mitigated.
            outcome = (
                "jailbroken"
                if response.get("success")
                else "mitigated"
                if response.get("success") is not None
                else "no verdict"
            )
            score = response.get("score")
            body = f"panel: {outcome}" + (
                f" (score {score:g})" if isinstance(score, (int, float)) else ""
            )
        else:
            text = response if response is not None else data.get("request")
            # A target reply is quoted as it is; a role's, by what it proposed.
            step["text"] = snippet(text if node.label == "target" else proposal(text))
            body = node.label + (f': "{step["text"]}"' if step["text"] else "")
        if node.error:
            body = f"{node.label} failed: {node.error}"
        if step["tokens"] is not None:
            body += f" · {step['tokens']} tok"
        if node.latency_s is not None:
            body += f" · {node.latency_s:.1f}s"
    else:
        body = node.label or node.node
    step["attempt"] = subject.get("attempt")
    step["goals"] = subject.get("goals")
    step["source"] = " · ".join(
        [str(step["attack"] or "run")]
        + (
            [goal_label(step["goal"], step["goals"])]
            if step["goal"] is not None
            else []
        )
        + ([f"attempt {step['attempt']}"] if step["attempt"] is not None else [])
    )
    step["what"] = body
    step["body"] = (" › ".join(within) + " › " if within else "") + body
    step["message"] = f"{step['source']} · {step['body']}"
    return step


def log_node(
    node: Any,
    subject: Mapping[str, Any],
    within: Sequence[str],
    label: Optional[str] = None,
) -> None:
    """Log one recorded node, if its level is enabled."""
    level = level_of(node)
    if level is None or not logger.isEnabledFor(level):
        return
    step = describe(node, subject, within, label)
    logger.log(level, "%s", step["message"], extra={"trace_step": step})


__all__ = ["describe", "level_of", "log_node", "proposal", "safe_details", "snippet"]
