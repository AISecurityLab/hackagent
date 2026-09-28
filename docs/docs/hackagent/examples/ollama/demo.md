---
sidebar_label: demo
title: hackagent.examples.ollama.demo
---

Minimal h4rm3l demo for an Ollama target model.

Target / Judge:
    gemma3:4b running on Ollama (http://localhost:11434)

The decorator program does not call an attacker model.

Prerequisites:
1. `pip install 'hackagent[hf,rag]'` — HarmBench is a Hub dataset, and
   h4rm3l imports NumPy from the `rag` extra. The TUI extra is not required.
2. Install Ollama: https://ollama.ai
3. Pull the target and judge model:
     ollama pull gemma3:4b
4. Start Ollama:
     ollama serve

Usage:
    python hackagent/examples/ollama/demo.py
    hackagent examples ollama

`hackagent examples ollama` runs this demo headless. It does not open the
terminal UI. `hackagent` and `hackagent tui` are a separate path.

#### build\_ollama\_demo\_config

```python
def build_ollama_demo_config() -> dict
```

Return the canonical Ollama h4rm3l demo configuration.

The standalone script and `hackagent examples ollama` both call this.
The terminal UI does not.

#### run\_ollama\_demo

```python
def run_ollama_demo() -> object
```

Run the Ollama h4rm3l demo through the client facade.

Settings come from :meth:`Settings.resolve`. The victim is bound with
:meth:`HackAgent.target`. The attack runs with :meth:`Target.hack`.

