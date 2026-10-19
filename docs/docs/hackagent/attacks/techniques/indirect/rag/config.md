---
sidebar_label: config
title: hackagent.attacks.techniques.indirect.rag.config
---

Configuration for the RAG poisoning attack.

## RagParams Objects

```python
class RagParams(AttackParams)
```

The corpus to poison, how to poison it, and who writes and embeds.

`attacker` writes the payloads and the benign queries; `embedder`
places the payloads and drives retrieval. Both are required: there is no
RAG attack without a corpus to search and a model to search it.

`documents` is that corpus, as raw text. File and PDF loading lived in
the old pipeline; a campaign passes the text directly, so a caller that
needs a file reads it first.

