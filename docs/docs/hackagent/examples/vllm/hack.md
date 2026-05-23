---
sidebar_label: hack
title: hackagent.examples.vllm.hack
---

Jailbreak risk evaluation for a vLLM-based agent.

Runs 100 tests with every supported attack (advprefix, flipattack, tap)
and prints a consolidated risk summary.

Prerequisites:
1. Install vLLM:
     pip install vllm

2. Start the victim model server (downloads from HuggingFace automatically):
     vllm serve Fastweb/FastwebMIIA-7B --host 0.0.0.0 --port 8000

3. Start the attacker/judge model server on a different port:
     vllm serve meta-llama/Llama-2-7b-chat-hf --host 0.0.0.0 --port 8001

   For gated models, set your HuggingFace token first:
     export HF_TOKEN=hf_...

vLLM exposes an OpenAI-compatible REST API, so agent_type is &quot;openai&quot;.

#### BATCH\_SIZE\_GENERATION

parallel prefix/completion requests (AdvPrefix)

#### BATCH\_SIZE\_JUDGE

parallel judge scoring requests (all attacks)

#### GOAL\_BATCH\_SIZE

goals processed per hack() call (1 = goal by goal)

