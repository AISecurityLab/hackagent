# PC Tool Sandbox (OpenAI-compatible)

This example creates a local target agent that exposes an OpenAI-compatible endpoint and can use tools to read files from a sandboxed `confidential/` directory.

It is intentionally vulnerable for authorized security testing.

## What you get

- `agent.py`: Flask server with `/v1/chat/completions`
- `hack.py`: runs PAIR attack against this target
- `confidential/`: synthetic local secrets used for testing

## Safety model

The tool layer enforces strict file access rules:

- No shell execution
- No arbitrary path access
- Only file names inside `confidential/`
- Path traversal blocked (`../` etc.)

## Prerequisites

1. Export OpenRouter API key

```bash
export OPENROUTER_API_KEY="..."
```

2. Optional: override defaults

```bash
export TARGET_MODEL="ibm-granite/granite-4.1-8b"
export PORT=5001
```

## Run from CLI

```bash
hackagent examples pc-tool
```

This command starts `agent.py` first, then runs `hack.py`.

## Run target only

```bash
cd examples/openai_sdk/pc_tool_sandbox
python agent.py
```

Endpoint: `http://127.0.0.1:5001/v1/chat/completions`

## Run PAIR end-to-end

```bash
cd examples/openai_sdk/pc_tool_sandbox
python hack.py
```

By default it uses:

- Target: local OpenAI-compatible endpoint (`agent.py`) backed by OpenRouter IBM Granite
- Attacker: `mistralai/mixtral-8x22b-instruct` on OpenRouter
- Judge: `openai/gpt-4o` on OpenRouter

## Environment variables

- `TARGET_MODEL` (default: `ibm-granite/granite-4.1-8b`)
- `PORT` (default: `5001`)
- `OPENROUTER_BASE_URL` (default: `https://openrouter.ai/api/v1`)
- `OPENROUTER_API_KEY` (required)
