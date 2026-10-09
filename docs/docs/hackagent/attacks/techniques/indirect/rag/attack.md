---
sidebar_label: attack
title: hackagent.attacks.techniques.indirect.rag.attack
---

RAG poisoning: write into the knowledge base, wait to be retrieved.

The target is a retrieval-augmented assistant: it answers from documents it
pulls out of a knowledge base. This attack never prompts it. It writes
adversarial text into the documents, lets a benign-looking question retrieve
that text into the model&#x27;s context, and measures whether the model followed
it. The target sees only an ordinary question and some context it trusts.

Per goal:

1. **queries** — the attacker writes benign questions, or they are given;
2. **poison** — for each query anchor, the attacker writes a payload and it
   is inserted next to the paragraph the anchor most resembles, so it rides
   the same retrieval. The embedder places it;
3. **index** — the poisoned corpus is chunked and embedded;
4. **retrieve** — each query retrieves its top chunks, they are attached to
   the question, the target answers, and the panel judges whether the
   poison landed.

Every query&#x27;s exchange is reported; there is no early stop, because the
point is the rate across queries, not the first hit.

The payload-framing subsystem (wrapping a payload in another technique) is
not carried over; it defaulted off. The three payload *strategies* are.

Based on PoisonedRAG: https://arxiv.org/abs/2402.07867

## Document Objects

```python
@dataclass
class Document()
```

One knowledge-base entry, and the payloads written into it.

## RagAttack Objects

```python
class RagAttack(IterativeAttack[RagParams])
```

Poison the retrieved corpus and judge what the target does with it.

