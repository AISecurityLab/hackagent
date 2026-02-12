# Corporate Policy RAG Agent

A RAG chatbot that answers employee questions about company policies.  
Tests whether prompt injection can exfiltrate **CONFIDENTIAL** documents that were accidentally indexed.

## Scenario

| Component | Description |
|-----------|-------------|
| **Agent** | CorpBot — a policy Q&A assistant using Ollama (Almawave/Velvet:2b) + RAG tool calling |
| **Document Store** | 10 legitimate policies + 5 confidential docs (salary bands, DB creds, PII, M&A, terminations) |
| **Risk** | Data exfiltration via prompt injection — the system prompt says "don't reveal CONFIDENTIAL" but that's the only guardrail |

## Usage

```bash
# 1. Install dependencies
pip install hackagent openai flask

# 2. Pull the model
ollama pull Almawave/Velvet:2b

# 3. Run (starts agent + attacks in one command)
cd examples/openai_sdk/rag
python hack.py
```

## Files

- **`knowledge_base.py`** — The RAG document store (policies + confidential docs)
- **`agent.py`** — The RAG agent (Flask server, OpenAI-compatible `/v1/chat/completions`)
- **`hack.py`** — Starts the agent + runs HackAgent attacks (AdvPrefix, Baseline, PAIR)
