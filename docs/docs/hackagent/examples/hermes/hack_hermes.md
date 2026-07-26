---
sidebar_label: hack_hermes
title: hackagent.examples.hermes.hack_hermes
---

Red-team a locally installed Hermes Agent instance.

This example drives Hermes Agent (Nous Research) natively through the ``hermes``
router provider — HackAgent shells out to the one-shot headless ``hermes -z``
CLI, so there is no HTTP endpoint or bridge to stand up. The only prerequisite
for the *target* is the ``hermes`` binary on PATH.

Hermes is stateful by design (long-term memory in ``~/.hermes/MEMORY.md``, a
background skill curator, resumable sessions). The adapter therefore forces an
isolated session for every attack turn: ``--ignore-user-config`` is passed by
default and ``--resume``/``--continue`` are never used, so the target can&#x27;t
&quot;learn&quot; from being probed and the operator&#x27;s real Hermes state stays clean.

It runs a small FlipAttack campaign. FlipAttack only needs a judge model,
running on the Anthropic API via LiteLLM here.

Prerequisites
-------------
1. Install Hermes Agent and confirm it runs:  ``hermes --version``
   (``curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash``)
2. Export an Anthropic key for the attacker/judge:  ``export ANTHROPIC_API_KEY=sk-ant-...``
3. Run:  ``python hack_hermes.py``

#### TARGET\_MODEL

passed to `hermes -m` for this run only

