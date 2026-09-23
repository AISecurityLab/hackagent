---
sidebar_label: config
title: hackagent.attacks.techniques.static_template.config
---

Configuration for static template attacks.

Static template attacks use predefined prompt patterns to attempt jailbreaks,
combining templates with goals to generate attack prompts.

#### validate\_template\_config

```python
def validate_template_config(config: Dict[str, Any]) -> None
```

Validate selected categories and substitutions without calling a model.

## TemplateAttackConfig Objects

```python
class TemplateAttackConfig(ConfigBase)
```

Configuration for static template attack pipeline.

#### evaluator\_type

Deprecated compatibility field

#### roles\_from\_mapping

```python
@classmethod
def roles_from_mapping(cls, data: Mapping[str, Any]) -> List[Dict[str, Any]]
```

Static template always needs judge models for LLM-judge evaluation.

#### from\_dict

```python
@classmethod
def from_dict(cls, config_dict: Dict[str, Any]) -> "TemplateAttackConfig"
```

Create config from dictionary.

#### to\_dict

```python
def to_dict() -> Dict[str, Any]
```

Convert to dictionary.

