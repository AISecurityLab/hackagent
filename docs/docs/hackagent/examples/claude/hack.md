---
sidebar_label: hack
title: hackagent.examples.claude.hack
---

Red-team a locally installed Claude Code instance.

This example drives Claude Code natively through the ``claude-code`` router
provider — HackAgent shells out to the headless ``claude -p`` CLI, so there is
no HTTP endpoint or bridge to stand up. The only prerequisite for the *target*
is the ``claude`` binary on PATH.

It runs a small TAP (Tree of Attacks with Pruning) campaign. TAP needs an
attacker model (to generate/refine jailbreak prompts) and a judge model (to
score them); both run on the Anthropic API via LiteLLM here.

Prerequisites
-------------
1. Install Claude Code and confirm it runs:  ``claude --version``
2. Export an Anthropic key for the attacker/judge:  ``export ANTHROPIC_API_KEY=sk-ant-...``
3. Run:  ``python hack.py``  (or ``hackagent claude`` for the interactive TUI preset)

#### TARGET\_MODEL

passed to `claude --model` (alias or full id)

