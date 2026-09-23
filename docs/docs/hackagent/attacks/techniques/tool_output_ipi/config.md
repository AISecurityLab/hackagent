---
sidebar_label: config
title: hackagent.attacks.techniques.tool_output_ipi.config
---

Configuration for tool-output indirect prompt injection (tool_output_ipi).

v1 focuses on **simulated** tool observations (InjecAgent / OPI style): a
benign user task would normally trigger a tool call; the attack appends a
``role=tool`` message whose content carries adversarial instructions aimed
at the malicious goal, then re-queries the target with the full history.

Taxonomy (when ``hackagent.catalog.taxonomy`` lands, `603` / `595`):
    Primary category: ``adaptive``
    Tags: ``indirect`` (do **not** also tag ``rag``)

Based on:
    - InjecAgent (ACL Findings 2024) — arXiv:2403.02691
    - AgentDojo (NeurIPS 2024) — arXiv:2406.13352
    - ASB OPI (ICLR 2025) — arXiv:2410.02644

## ToolOutputIPIParams Objects

```python
class ToolOutputIPIParams(BaseModel)
```

Hyperparameters for tool-output indirect prompt injection.

## ToolOutputIPIConfig Objects

```python
class ToolOutputIPIConfig(ConfigBase)
```

Full typed configuration for the tool_output_ipi attack.

#### roles\_from\_mapping

```python
@classmethod
def roles_from_mapping(cls, data: Mapping[str, Any]) -> List[Dict[str, Any]]
```

Attacker only when ``use_attacker_llm`` is enabled; judges always.

#### from\_dict

```python
@classmethod
def from_dict(cls, config_dict: Dict[str, Any]) -> "ToolOutputIPIConfig"
```

Create a :class:`ToolOutputIPIConfig` from a plain dictionary.

#### to\_dict

```python
def to_dict() -> Dict[str, Any]
```

Convert to dictionary suitable for :meth:`HackAgent.hack`.

