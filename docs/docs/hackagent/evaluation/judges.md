---
sidebar_label: judges
title: hackagent.evaluation.judges
---

Judge types: prompt templates and parsers.

Each type turns a :class:`~hackagent.core.contracts.Sample` into a prompt
and a model reply into a native score. Calling the model is
:class:`~hackagent.evaluation.panel.LLMJudge`&#x27;s job, through the core
``LLM`` protocol.

#### infer\_judge\_type

```python
def infer_judge_type(identifier: Optional[str],
                     default: Optional[str] = None) -> Optional[str]
```

Infer a judge type key from a model identifier.

#### parse\_yes\_no

```python
def parse_yes_no(content: Optional[str],
                 *,
                 yes_label: str = "Success",
                 no_label: str = "Safe",
                 judge_name: str = "Judge") -> AssertionResult
```

Parse a yes/no classifier reply, most-confident strategies first.

#### extract\_decimal\_score

```python
def extract_decimal_score(content: Optional[str]) -> Optional[int]
```

Pull a 0-10 rating out of common scorer formats.

## RagOutcomeJudge Objects

```python
class RagOutcomeJudge(_JudgeType)
```

Whether a RAG response advances a poisoned goal. Registered as ``rag_outcome``.

#### judge\_type

```python
def judge_type(name: str) -> _JudgeType
```

Build the registered judge type for ``name``.

