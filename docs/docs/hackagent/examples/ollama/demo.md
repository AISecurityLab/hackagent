---
sidebar_label: demo
title: hackagent.examples.ollama.demo
---

Minimal h4rm3l demo for an Ollama target model.

Target / Judge:
    gemma3:4b running on Ollama (http://localhost:11434)

Prerequisites:
1. Install Ollama: https://ollama.ai
2. Pull required models:
     ollama pull gemma3:4b
3. Start Ollama:
     ollama serve

Usage:
    python demo.py
    python -m examples.ollama.demo

#### build\_ollama\_demo\_config

```python
def build_ollama_demo_config() -> dict
```

Return the canonical Ollama FlipAttack demo configuration.

This single source is reused by standalone script execution and CLI/TUI
entrypoints, so edits here are reflected everywhere.

#### run\_ollama\_demo

```python
def run_ollama_demo() -> object
```

Execute the Ollama FlipAttack demo and return results.

