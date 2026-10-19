# Corporate Policy RAG Agent

A RAG chatbot that answers employee questions about company policies.  
Tests whether prompt injection can exfiltrate **CONFIDENTIAL** documents that were accidentally indexed.

## Scenario

| Component | Description |
|-----------|-------------|
| **Agent** | CorpBot — a policy Q&A assistant using OpenRouter (`ibm-granite/granite-4.1-8b`) + RAG |
| **Document Store** | 10 legitimate policies + 5 confidential docs (salary bands, DB creds, PII, M&A, terminations) |
| **Risk** | Data exfiltration via prompt injection — the system prompt says "don't reveal CONFIDENTIAL" but that's the only guardrail |

## Usage

```bash
# 1. Install dependencies
pip install langchain-openai langchain-community langchain-classic langchain-text-splitters faiss-cpu fastapi uvicorn pypdf

# 2. Export OpenRouter API key
export OPENROUTER_API_KEY="..."

# 3. Build vector index (if missing)
cd examples/openai_sdk/rag
python ingest.py

# 4. Run the OpenAI-compatible RAG server
python agent_server.py

# 5. Run the attack
hackagent campaign run h4rm3l-corpbot.yaml
```

The attack is a campaign file, so you can read it end to end and change the
goals, the decorator program or the judge without touching Python.
`hackagent campaign validate h4rm3l-corpbot.yaml` checks it without attacking.

Note: `hackagent examples rag` runs a different, fully-local example (no API key
required) — see `hackagent/examples/rag/indirect-injection.yaml`. Start this
example's server as shown above, then run its campaign.

## Files

- **`agent_server.py`** — OpenAI-compatible RAG server using IBM Granite on OpenRouter
- **`ingest.py`** — Creates local FAISS index from `policies.pdf`
- **`h4rm3l-corpbot.yaml`** — The attack: h4rm3l against the local RAG endpoint
