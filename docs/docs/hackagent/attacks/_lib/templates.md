---
sidebar_label: templates
title: hackagent.attacks._lib.templates
---

Shared attack templates library.

This module provides reusable attack prompt templates that can be used
across different objectives and techniques.

Classes:
    AttackTemplates: Centralized library of attack prompt templates

Constants:
    REFUSAL_PATTERNS: Regex patterns for detecting model refusals
    SUCCESS_PATTERNS: Regex patterns for detecting successful attacks

Usage:
    from hackagent.attacks._lib.templates import (
        AttackTemplates,
        REFUSAL_PATTERNS,
        SUCCESS_PATTERNS,
    )

## AttackTemplates Objects

```python
class AttackTemplates()
```

Centralized library of attack prompt templates.

Templates are organized by attack pattern/category and can be
used by multiple objectives and techniques.

#### get\_by\_category

```python
@classmethod
def get_by_category(cls, category: str) -> List[str]
```

Get templates for a specific category.

**Arguments**:

- `category` - Template category name
  

**Returns**:

  List of template strings

#### get\_all\_categories

```python
@classmethod
def get_all_categories(cls) -> List[str]
```

Get list of all available template categories.

#### apply\_template

```python
@classmethod
def apply_template(cls, template: str, goal: str, **kwargs) -> str
```

Apply a template with goal and optional additional parameters.

**Arguments**:

- `template` - Template string with placeholders
- `goal` - Goal to insert into template
- `**kwargs` - Additional template parameters, overriding generated values.
  Translations must be supplied explicitly; none are generated.
  

**Returns**:

  Formatted attack prompt
  

**Raises**:

- `ValueError` - If a required parameter is missing or formatting is invalid.
  
  ``goal_encoded`` uses ROT13, ``goal_base64`` uses UTF-8 Base64, and
  ``goal_obfuscated`` reverses the goal&#x27;s Unicode code points.

#### generate\_variations

```python
@classmethod
def generate_variations(cls,
                        template: str,
                        goal: str,
                        num_variations: int = 3) -> List[str]
```

Generate variations of a template.

**Arguments**:

- `template` - Base template string
- `goal` - Goal to insert
- `num_variations` - Number of variations to generate
  

**Returns**:

  List of template variations

