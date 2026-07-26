---
sidebar_position: 8
---

# Scan

`hackagent scan <url>` red-teams a website's chatbot widget through a **real browser** — it drives the live page, typing each prompt into the chat widget and reading the reply from the page. Because it works at the DOM level, it works against any chat UI regardless of transport (WebSocket, SSE, plain HTTP).

## Usage

```bash
hackagent scan https://www.example.com
hackagent scan https://www.example.com --plan
hackagent scan https://www.example.com --headed --input-selector 'textarea'
hackagent scan https://www.example.com --config-file goals.yaml --no-tui
hackagent scan https://www.example.com --no-attack --json
```

## Options

| Option | Default | Description |
|---|---|---|
| `--headed` | `False` | Show the browser window instead of running headless |
| `--input-selector` | — | CSS selector pinning the chat input box, if heuristics can't find it |
| `--reply-selector` | — | CSS selector pinning the bot's reply element, skipping the DOM-diff heuristic |
| `--open-selector` | — | CSS selector for a collapsed chat-launcher bubble to click first |
| `--accept-cookies` / `--no-accept-cookies` | `True` | Accept/dismiss a cookie-consent banner on load |
| `--llm-fallback-model` | — | LiteLLM model used to read the reply from the page only when DOM heuristics find nothing |
| `--install-browser` / `--no-install-browser` | `True` | Auto-download Chromium (~150 MB, one-time) if missing |
| `--timeout` | `45` | Page-load timeout in seconds |
| `--json` | `False` | Print the target config (and plan, if any) as JSON and exit |
| `--plan` | `False` | Agentic mode: an LLM inspects the target and chooses the attack strategy and parameters |
| `--planner-model` | `ollama_chat/huihui_ai/gemma-4-abliterated:12b` | LiteLLM model for the `--plan` planner (defaults to a local Ollama model, no API key needed) |
| `--attack` / `--no-attack` | `True` | Red-team the target; `--no-attack` just shows the resolved config |
| `--config-file` | — | YAML/JSON file supplying `goals:` plus optional `attacker`, `judge`, `category_classifier`, `parameters`, `attack_type` |
| `--goals` | — | Attack goals; repeat `--goals` or pass a comma-separated string |
| `--attack-type` | `pair` | Attack strategy (`tap`, `pair`, `flipattack`, `advprefix`, …); ignored when `--plan` picks one |
| `--attacker-model` | — | Override the attacker LLM with any LiteLLM model id (e.g. `openai/gpt-4o-mini`) |
| `--judge-model` | — | Override the judge/scorer LLM with any LiteLLM model id |
| `--attack-timeout` | `300` | Attack timeout in seconds |
| `--no-tui` | `False` | Run the attack headless instead of opening the TUI |
| `--dry-run` | `False` | Validate the wiring without executing (implies `--no-tui`) |

## See Also

- [Attack](./attack.mdx) — Run attacks via the SDK-driven `eval` commands (for agents you already control programmatically)
- [Agents: Guardrails](../agents/guardrails.mdx) — Add before/after guardrails to any attack
