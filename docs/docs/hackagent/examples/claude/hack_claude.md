---
sidebar_label: hack_claude
title: hackagent.examples.claude.hack_claude
---

Red-team a locally installed Claude Code instance.

This example drives Claude Code natively through the ``claude-code`` router
provider — HackAgent shells out to the headless ``claude -p`` CLI, so there is
no HTTP endpoint or bridge to stand up. The only prerequisite for the *target*
is the ``claude`` binary on PATH.

It runs a small FlipAttack campaign. FlipAttack only needs a judge model, running
on the Anthropic API via LiteLLM here.

Prerequisites
-------------
1. Install Claude Code and confirm it runs:  ``claude --version``
2. Export an Anthropic key for the attacker/judge:  ``export ANTHROPIC_API_KEY=sk-ant-...``
3. Run:  ``python hack_claude.py``  (or ``hackagent claude`` for the interactive TUI preset)

#### TARGET\_MODEL

passed to `claude --model` (alias or full id)

