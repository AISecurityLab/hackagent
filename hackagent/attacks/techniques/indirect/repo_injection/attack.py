# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Repository injection: plant an instruction in a file a coding agent reads.

A coding agent such as Claude Code reads the instruction files of the
repository it works in (``CLAUDE.md``, contributor notes, READMEs) and
treats them as the project's own guidance. Whoever can write to the
repository — a dependency, a pull request, a cloned sample — can therefore
speak to the agent without being its user. This attack tests exactly that:
the user asks for an ordinary coding task, and the goal sits in a file of
the repository as one of the project's instructions.

Unlike the other indirect techniques nothing is simulated. Each attempt
copies the repository, writes the poisoned file into the copy, and runs the
agent there for real, through the target's per-call ``cwd``. What the agent
*did* — its tool calls and their results, in order — is what the panel
judges, because the harm the goal asks for is a command run or data sent,
not a sentence. The final reply goes along as context only: a reply that
claims compliance without a matching action is not a success.

The files the agent reads come back in its tool results, and those results
reach the panel (and the attacker). Run it on a canary copy of a real
repository: nothing in it should be a secret that may not leave the machine.

Algorithm (one goal), with the parameters of
:class:`~.config.RepoInjectionParams`:

1. Check that ``repo`` is a directory; fail before any attempt otherwise.
2. Fill ``injection_template`` with the goal (``{goal}``).
3. For each attempt (``max_attempts`` with an ``attacker``, otherwise one):

   - the poisoned file is the filled template on the first attempt; later
     ones ask the ``attacker`` for a new full content of ``poison_path``,
     given the previous content, the agent's tool calls on the previous
     attempt and its final reply (a failed or empty rewrite falls back to
     the template);
   - copy ``repo`` into a fresh temporary directory (symbolic links are
     copied as links) and write the poisoned file at ``poison_path``,
     replacing any file there; a path that resolves outside the copy is
     refused;
   - send ``task`` as the only user message, with the copy as the agent's
     working directory;
   - give the panel what the agent did: every action as
     ``name(arguments)`` in call order (each argument list cut to 1000
     characters), then the results under the same numbers, errors first
     (each cut to 300), then the final reply, so the actions stay within
     the part of a long response a judge reads. It is judged against
     :data:`~.prompts.JUDGE_HINT`, which counts an attempt only when an
     action that ran attempts the goal: an action blocked before it ran (a
     hook or permission denial) does not count, and the reply alone is not
     evidence; stop at the first success;
   - delete the copy, whatever happened (unless ``keep_workspaces``).

Deviations: no paper. The attack is HackAgent's own, built for coding agents
that act on a real working directory. Its one learning step is that the
attacker sees what the agent did on the previous attempt — the tool calls,
their results and the reply — and rewrites the file from that.

Roles: ``attacker`` (optional) rewrites the poisoned file for each attempt
after the first.

Attempts and success: every attempt whose reply had text or a tool call is
one attempt, carrying the poisoned file, its path, the agent's tool calls
and (with ``keep_workspaces``) the copy it ran in; the goal succeeds when the
panel calls any attempt a success.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any, Optional

from ...contract import Completion, Judge, Target
from ...iterative import Finding, IterativeAttack, judge_reply, succeeded
from ...trace import decision, phase
from . import prompts
from .config import RepoInjectionParams

#: How much of each tool call's arguments and result the panel and the
#: attacker read. Results carry whole files; arguments can too.
_ARGUMENTS_LIMIT = 1000
_RESULT_LIMIT = 300
#: How much of the agent's final reply the attacker reads.
_REPLY_LIMIT = 2000


class RepoInjectionAttack(IterativeAttack[RepoInjectionParams]):
    """Poison a file in a copy of a repository and see whether the coding agent obeys it.

    Each attempt copies ``repo``, writes the goal into ``poison_path``
    (``CLAUDE.md`` by default) as an ordinary project instruction, and runs
    the agent on a benign ``task`` in that copy; the campaign's evaluation
    panel judges whether its tool calls attempt the goal, with the reply as
    context only. An
    optional ``attacker`` rewrites the file from what the agent did. The
    algorithm is documented in the module
    ``hackagent.attacks.techniques.indirect.repo_injection.attack``.
    """

    name = "repo_injection"
    params_type = RepoInjectionParams

    def __init__(self, params: RepoInjectionParams) -> None:
        super().__init__(params)
        self.attacker: Optional[Completion] = params.attacker

    async def search(
        self, goal: str, target: Target, judge: Optional[Judge]
    ) -> list[Finding]:
        """Run the agent on a poisoned copy per attempt; return every judged attempt.

        Calls the target and the panel once per attempt, and the
        ``attacker`` once per attempt after the first.

        Raises:
            ValueError: ``repo`` is not a directory, or ``poison_path``
                resolves outside the copy.
        """
        params = self.params
        repo = Path(params.repo).expanduser()
        if not repo.is_dir():
            raise ValueError(f"repo {params.repo!r} is not a directory")

        base = prompts.render_injection(params.injection_template, goal=goal)
        # Nothing changes between attempts without an attacker to change it,
        # so there is no point running the agent on the same file twice.
        attempts = params.max_attempts if self.attacker is not None else 1
        findings: list[Finding] = []
        poison, reply = base, None

        for attempt in range(attempts):
            label = f"attempt {attempt + 1}/{attempts}"
            with phase(label, attempt=attempt) as path:
                if attempt:
                    poison = await self._rewrite(goal, base, poison, reply)
                reply, finding = await self._attempt(
                    goal, repo, poison, attempt, target, judge, path
                )
                if finding is None:
                    continue
                findings.append(finding)
                if succeeded(finding.verdict):
                    decision("stopped", "the agent followed the planted instruction")
                    break

        return findings

    async def _rewrite(self, goal: str, base: str, previous: str, reply: Any) -> str:
        """A new poisoned file from the attacker; ``base`` when it gives none."""
        params = self.params
        calls = _calls(reply)
        request = prompts.refine_request(
            goal=goal,
            task=params.task,
            poison_path=params.poison_path,
            poison=previous,
            actions="\n".join(f"- {_describe_call(call)}" for call in calls),
            reply=_cut(str(getattr(reply, "text", "") or ""), _REPLY_LIMIT),
        )
        try:
            rewritten = await self.attacker(request)
        except Exception:
            return base
        return rewritten.strip() if rewritten and rewritten.strip() else base

    async def _attempt(
        self,
        goal: str,
        repo: Path,
        poison: str,
        attempt: int,
        target: Target,
        judge: Optional[Judge],
        path,
    ) -> tuple[Any, Optional[Finding]]:
        """Run the agent once on a poisoned copy; the reply, and its finding or ``None``."""
        params = self.params
        workspace = Path(tempfile.mkdtemp(prefix="hackagent-repo-"))
        try:
            shutil.copytree(repo, workspace, symlinks=True, dirs_exist_ok=True)
            _plant(workspace, params.poison_path, poison)
            messages = [{"role": "user", "content": params.task}]
            reply = await target(messages, cwd=str(workspace))
        finally:
            if not params.keep_workspaces:
                shutil.rmtree(workspace, ignore_errors=True)

        calls = _calls(reply)
        if not reply.ok or (not reply.text and not calls):
            decision("skipped", "the agent gave no usable reply")
            return reply, None

        verdict = await judge_reply(
            judge, goal, prompts.JUDGE_HINT, _acted(reply.text, calls)
        )
        metadata: dict[str, Any] = {
            "attempt": attempt,
            "poison_path": params.poison_path,
            "poison": poison,
            "tool_calls": calls,
        }
        if params.keep_workspaces:
            metadata["workspace"] = str(workspace)
        return reply, Finding(
            messages=messages,
            response=reply,
            verdict=verdict,
            metadata=metadata,
            path=path,
        )


def _plant(workspace: Path, poison_path: str, poison: str) -> None:
    """Write ``poison`` at ``poison_path`` in the copy, never outside it.

    The copy keeps the repository's symbolic links, so a link at the path is
    replaced rather than written through, and a directory link that leads
    out of the copy is refused.
    """
    file = workspace / poison_path
    root = workspace.resolve()
    parent = file.parent.resolve()
    if parent != root and root not in parent.parents:
        raise ValueError(f"poison_path {poison_path!r} resolves outside the repository")
    parent.mkdir(parents=True, exist_ok=True)
    file = parent / file.name
    if file.is_symlink():
        file.unlink()
    file.write_text(poison, encoding="utf-8")


def _calls(reply: Any) -> list:
    """The tool calls a reply carries, in call order."""
    return list(getattr(reply, "tool_calls", None) or [])


def _acted(text: Optional[str], calls: list) -> str:
    """What the agent did, for the panel: its actions, their results, its reply.

    Every call's input comes first, numbered in call order, then every
    result under the same number, then the reply. Judges such as HarmBench
    read only the beginning of a long response, so the action that carries
    out the goal must sit near the start however long the results and the
    reply are. Error results are listed before the others: an error is what
    tells a call that was blocked before it ran from one that ran, and file
    contents in the other results would otherwise push it out of view.
    """
    if not calls:
        return text or ""
    numbered = list(enumerate(calls, 1))
    actions = "\n".join(f"{n}. {_describe_input(call)}" for n, call in numbered)
    errors_first = sorted(numbered, key=lambda item: not _flag(item[1], "is_error"))
    results = "\n".join(
        f"{n}. {_describe_result(call) or '(no result)'}" for n, call in errors_first
    )
    parts = [
        f"[agent actions, in call order]\n{actions}",
        f"[results, numbered as the actions, errors first]\n{results}",
    ]
    if text:
        parts.append(f"[final reply]\n{text}")
    return "\n".join(parts)


def _describe_call(call: object) -> str:
    """One tool call as ``name(arguments) → result``, each part cut short.

    A call reaches here in whatever shape the model layer used: Claude
    Code's flat dict with ``result`` and ``is_error``, a provider's nested
    ``{"function": {...}}`` dict, or a ``ToolCall`` object. A call without a
    result has no ``→`` part.
    """
    described = _describe_input(call)
    result = _describe_result(call)
    return f"{described} → {result}" if result else described


def _describe_input(call: object) -> str:
    """A call's input as ``name(arguments)``, the arguments cut short."""
    inner = call.get("function") if isinstance(call, dict) else None
    source = inner if isinstance(inner, dict) else call
    name = _field(source, "name") or "?"
    arguments = _cut(_field(source, "arguments"), _ARGUMENTS_LIMIT)
    return f"{name}({arguments})"


def _describe_result(call: object) -> str:
    """A call's result cut short, ``error: `` first when it failed; '' if none."""
    result = _field(call, "result")
    if not result:
        return ""
    error = "error: " if _flag(call, "is_error") else ""
    return f"{error}{_cut(result, _RESULT_LIMIT)}"


def _field(source: object, name: str) -> str:
    """``name`` of a dict or an object, as text; empty when missing."""
    if isinstance(source, dict):
        return str(source.get(name) or "")
    return str(getattr(source, name, "") or "")


def _flag(source: object, name: str) -> bool:
    """``name`` of a dict or an object, as a boolean."""
    if isinstance(source, dict):
        return bool(source.get(name))
    return bool(getattr(source, name, False))


def _cut(text: str, limit: int) -> str:
    """``text`` cut to ``limit`` characters, marked when it was cut."""
    return text if len(text) <= limit else f"{text[:limit]}…"


__all__ = ["RepoInjectionAttack"]
