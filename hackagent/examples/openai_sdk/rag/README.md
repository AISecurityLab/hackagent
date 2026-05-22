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

# 3. Run end-to-end from HackAgent CLI
hackagent examples rag

# The command does this automatically:
# - run ingest.py only if db_index/ is missing
# - start agent_server.py
# - run hack.py
```

Manual flow (equivalent):

```bash
# 1. Build vector index (if missing)
cd examples/openai_sdk/rag
python ingest.py

# 2. Run the OpenAI-compatible RAG server
python agent_server.py

# 3. Run attack example
python hack.py
```

## Files

- **`agent_server.py`** — OpenAI-compatible RAG server using IBM Granite on OpenRouter
- **`ingest.py`** — Creates local FAISS index from `policies.pdf`
- **`hack.py`** — Attack driver example against the local RAG endpoint
