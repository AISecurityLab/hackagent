---
sidebar_label: hack_codex
title: hackagent.examples.codex.hack_codex
---

Red-team a locally installed Codex CLI instance.

This example drives the target natively through the ``codex`` router
provider. HackAgent shells out directly to the non-interactive Codex CLI
(``codex exec`` / ``codex e``), so there is no Ollama server, HTTP endpoint,
or bridge process to run. The target only needs the ``codex`` binary available
on PATH, plus whatever authentication the Codex CLI normally requires.

The ``endpoint`` value passed to ``HackAgent`` is only a placeholder required by
the remote-agent configuration shape; it is not used to contact Codex.

This script runs a small h4rm3l campaign against the local Codex target. The
judge is configured through LiteLLM, so make sure the environment contains the
credentials required by the selected judge model.

Prerequisites
-------------
1. Install Codex and confirm it runs:  ``codex --version``
2. Make sure Codex CLI is authenticated and can run non-interactively.
3. Export the credentials required by the LiteLLM judge model.
4. Run:  ``python hack_codex.py``  (or ``hackagent codex`` for the interactive TUI preset)

#### TARGET\_MODEL

passed to Codex CLI via -m

