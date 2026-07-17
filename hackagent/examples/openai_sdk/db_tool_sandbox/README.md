# DB Tool Sandbox (Ollama + SQLite)

This example creates a local target agent that exposes an OpenAI-compatible endpoint and gives the LLM real database access through explicit tools.

It is designed for authorized red-team testing of:

- tool abuse against a DB-enabled LLM agent
- policy bypass attempts for sensitive-table access
- prompt-injection style attacks against tool selection

## What you get

- `agent.py`: Flask server with `/v1/chat/completions`
- `hack.py`: runs PAIR against this target
- `sandbox.db`: local SQLite test database (auto-created and seeded)

## Architecture

- Target LLM: local Ollama model (via OpenAI-compatible API)
- Tool layer: `list_tables`, `describe_table`, `run_sql_query`
- Database: local SQLite file (real DB engine, read-only query enforcement)

## Prerequisites

1. Start Ollama and pull models

```bash
ollama pull qwen2.5:7b
ollama pull gemma3:4b
ollama serve
```

2. Install Python deps (if not already installed in your env)

```bash
pip install flask openai hackagent
```

## Run target

```bash
cd hackagent/examples/openai_sdk/db_tool_sandbox
python agent.py
```

Endpoint: `http://127.0.0.1:5002/v1/chat/completions`

## Run FlipAttack end-to-end

```bash
cd hackagent/examples/openai_sdk/db_tool_sandbox
python hack.py
```

## Environment variables

- `PORT` (default: `5002`)
- `DB_PATH` (default: `./sandbox.db`)
- `TARGET_MODEL` (default: `qwen2.5:7b`)
- `OLLAMA_BASE_URL` (default: `http://localhost:11434/v1`)
- `OLLAMA_ENDPOINT` (default: `http://localhost:11434`)
- `ATTACKER_MODEL` (default: `gemma3:4b`)
- `JUDGE_MODEL` (default: `gemma3:4b`)
- `EXPOSE_SENSITIVE_TABLES` (default: `1`)
- `HACKAGENT_DB_TOOL_EXTERNAL_AGENT` (default: unset)

## Notes

- This sandbox is intentionally configured for security testing, not production.
- Only run attacks against systems you are authorized to test.
