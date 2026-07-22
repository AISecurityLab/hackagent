---
sidebar_label: hack_ollama
title: hackagent.examples.codex.hack_ollama
---

Red-team a locally installed Codex instance launched by Ollama, e.g. using
a local Ollama model as the backend.

This example drives Codex natively through the ``codex`` router
provider — HackAgent shells out to the headless ``ollama launch codex --`` CLI, so there is
no HTTP endpoint or bridge to stand up. The only prerequisite for the *target*
is the ``ollama`` binary on PATH.

This script runs a small h4rm3l campaign against the local Codex target.

Prerequisites
-------------
1. Install Codex and confirm it runs:  ``codex --version``
2. Install Ollama and confirm it runs:  ``ollama --version``
3. Run:  ``python hack_ollama.py``  (or ``hackagent codex`` for the interactive TUI preset)

#### OLLAMA\_ENDPOINT

Ollama default endpoint for local models

