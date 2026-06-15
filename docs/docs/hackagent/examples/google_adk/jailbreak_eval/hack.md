---
sidebar_label: hack
title: hackagent.examples.google_adk.jailbreak_eval.hack
---

Jailbreak risk evaluation of a Gemini-powered Google ADK agent.

Runs the HarmBench benchmark against the agent using the AdvPrefix attack
and evaluates results with a HarmBench judge.

Prerequisites:
    pip install hackagent google-adk
    export OPENROUTER_API_KEY=&quot;...&quot;   # for the Gemini agent via OpenRouter
    export HACKAGENT_API_KEY=&quot;...&quot;    # or configure via ~/.config/hackagent/config.json

Usage:
    python hack.py

#### start\_adk\_server

```python
def start_adk_server()
```

Start `adk api_server` as a subprocess and wait until it&#x27;s ready.

