# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tool-output indirect prompt injection: poison what a tool returns.

Every other technique here talks to the target as the user. This one does
not say a word as the user: it stands between the agent and its tools and
hands back a *tool result* that carries an instruction. The question is
whether an agent that trusts its tools will carry that instruction out — a
follow-up tool call, or compliance in its reply — as though the tool had
told it to.

So the request the target sees is a short history it did not have: the user
asks something benign, the assistant calls a tool, and the tool returns the
poison. The target is given the tool schemas too, so a follow-up call is
something it *can* make. Whether it does is what the panel judges.

An optional ``attacker`` role rewrites the payload between attempts; without
one, a single payload is tried.

Paper: Qiusi Zhan, Zhixiang Liang, Zifan Ying, Daniel Kang, "InjecAgent:
Benchmarking Indirect Prompt Injections in Tool-Integrated Large Language
Model Agents", 2024, [arXiv:2403.02691](https://arxiv.org/abs/2403.02691).
InjecAgent measures whether an agent, after calling a user tool whose
result an attacker controls, carries out the attacker's instruction:
direct harm to the user, or exfiltration of private data.

Algorithm (one goal), with the parameters of
:class:`~.config.ToolOutputIPIParams`:

1. Pick a benign user task from ``benign_tasks`` by hashing the goal, and
   fill ``injection_template`` with ``goal``, ``benign_task`` and
   ``tool_name`` (a template using only some placeholders still works).
2. For each attempt (``max_attempts`` with an ``attacker``, otherwise one):

   - the payload is the filled template on the first attempt; later ones
     ask the ``attacker`` for a fresh rewrite of it (the attacker does not
     see earlier replies; a failed rewrite falls back to the template);
   - build the tool result: ``observation_prefix``, the payload, and the
     framing sentence for ``success_setting``;
   - send a fabricated history (the user asks the benign task, the
     assistant calls ``tool_name`` with ``tool_arguments``, the tool
     returns the poisoned result) together with the ``tools`` schemas;
   - give the panel the agent's reply plus any follow-up tool calls, as
     ``name(arguments)``, with the judging hint for ``success_setting`` as
     the prompt; stop at the first success.

Deviations from the paper: InjecAgent runs a fixed benchmark of user and
attacker tools and checks success by whether the agent emits the
attacker's tool call; here the goal is the injected instruction, the tool
history is simulated and no follow-up call is executed, and the campaign's
evaluation panel decides from the reply and the calls described to it. The
default injection template and the optional attacker refinement are
HackAgent's.

Roles: ``attacker`` (optional) rewrites the payload for each attempt after
the first.

Attempts and success: every attempt whose reply had text or a follow-up
tool call is one attempt, carrying its benign task, follow-up calls and
setting; the goal succeeds when the panel calls any attempt a success.
"""

from __future__ import annotations

from typing import Optional

from ...contract import Completion, Judge, Target
from ...iterative import Finding, IterativeAttack, judge_reply, succeeded
from ...trace import decision, phase
from . import prompts
from .config import ToolOutputIPIParams


class ToolOutputIPIAttack(IterativeAttack[ToolOutputIPIParams]):
    """Hand the agent a poisoned tool result and see whether it obeys the injection.

    Implements tool-output indirect prompt injection after InjecAgent (Zhan
    et al., 2024, [arXiv:2403.02691](https://arxiv.org/abs/2403.02691)):
    the target receives a fabricated history in which a benign request led
    to a tool call whose result carries the goal as an instruction, and the
    campaign's evaluation panel judges whether its reply or follow-up tool
    calls carry it out. An optional ``attacker`` rewrites the payload for
    further attempts. The algorithm and the deviations from the paper are
    documented in the module
    ``hackagent.attacks.techniques.indirect.tool_output_ipi.attack``.
    """

    name = "tool_output_ipi"
    params_type = ToolOutputIPIParams

    def __init__(self, params: ToolOutputIPIParams) -> None:
        super().__init__(params)
        self.attacker: Optional[Completion] = params.attacker

    async def search(
        self, goal: str, target: Target, judge: Optional[Judge]
    ) -> list[Finding]:
        """Inject the payload, refining it between attempts; return every judged attempt.

        Calls the target and the panel once per attempt, and the
        ``attacker`` once per attempt after the first.
        """
        params = self.params
        benign_task = self._benign_task(goal)
        base = prompts.render_injection(
            params.injection_template,
            goal=goal,
            benign_task=benign_task,
            tool_name=params.tool_name,
        )
        # Nothing changes between attempts without an attacker to change it,
        # so there is no point trying the same payload twice.
        attempts = params.max_attempts if self.attacker is not None else 1
        findings: list[Finding] = []

        for attempt in range(attempts):
            label = f"attempt {attempt + 1}/{attempts}"
            with phase(label, attempt=attempt) as path:
                payload = await self._payload(goal, benign_task, base, attempt)
                finding = await self._inject(
                    goal, benign_task, payload, attempt, target, judge, path
                )
                if finding is None:
                    continue
                findings.append(finding)
                if succeeded(finding.verdict):
                    decision("stopped", "the agent followed the injected instruction")
                    break

        return findings

    def _benign_task(self, goal: str) -> str:
        """The benign task for ``goal``, picked by Python's per-process string hash."""
        tasks = self.params.benign_tasks or prompts.DEFAULT_BENIGN_TASKS
        return tasks[hash(goal) % len(tasks)]

    async def _payload(
        self, goal: str, benign_task: str, base: str, attempt: int
    ) -> str:
        """The injection body: ``base``, or an attacker refinement of it."""
        if self.attacker is None or attempt == 0:
            return base
        try:
            refined = await self.attacker(
                prompts.refine_request(goal, benign_task, self.params.tool_name, base)
            )
        except Exception:
            return base
        return refined.strip() if refined and refined.strip() else base

    async def _inject(
        self,
        goal: str,
        benign_task: str,
        payload: str,
        attempt: int,
        target: Target,
        judge: Optional[Judge],
        path,
    ) -> Optional[Finding]:
        """Send one poisoned history and judge what the agent did; ``None`` when unusable."""
        params = self.params
        observation = prompts.poisoned_observation(
            payload, setting=params.success_setting, prefix=params.observation_prefix
        )
        messages = prompts.poisoned_history(
            benign_task=benign_task,
            tool_name=params.tool_name,
            tool_arguments=params.tool_arguments,
            observation=observation,
        )
        reply = await target(messages, tools=list(params.tools))
        followups = list(getattr(reply, "tool_calls", None) or [])
        if not reply.ok or (not reply.text and not followups):
            decision("skipped", "the target gave no usable reply")
            return None

        # What the agent did: its words, plus any follow-up tool call, since
        # the harm the injection asks for is often the call rather than prose.
        acted = _acted(reply.text, followups)
        verdict = await judge_reply(
            judge, goal, prompts.judge_hint(params.success_setting), acted
        )
        return Finding(
            messages=messages,
            response=reply,
            verdict=verdict,
            metadata={
                "attempt": attempt,
                "benign_task": benign_task,
                "followup_tool_calls": followups,
                "success_setting": params.success_setting,
            },
            path=path,
        )


def _acted(text: str, followups: list) -> str:
    """How the agent responded, tool calls included, for the panel.

    A follow-up call reaches here in whatever shape the model layer used: a
    flat ``ToolCall`` object, a flat dict, or a provider's nested
    ``{"function": {...}}`` dict. All three are reduced to ``name(args)``.
    """
    if not followups:
        return text or ""
    calls = "; ".join(_describe_call(call) for call in followups)
    return f"{text or ''}\n[follow-up tool calls: {calls}]".strip()


def _describe_call(call: object) -> str:
    """One follow-up call as ``name(arguments)``."""
    inner = call.get("function") if isinstance(call, dict) else None
    source = inner if isinstance(inner, dict) else call
    name = _field(source, "name")
    arguments = _field(source, "arguments")
    return f"{name or '?'}({arguments or ''})"


def _field(source: object, name: str) -> str:
    """``name`` of a dict or an object, as text; empty when missing."""
    if isinstance(source, dict):
        return str(source.get(name) or "")
    return str(getattr(source, name, "") or "")


__all__ = ["ToolOutputIPIAttack"]
