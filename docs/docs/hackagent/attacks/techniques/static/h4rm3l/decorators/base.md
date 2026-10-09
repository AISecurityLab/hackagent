---
sidebar_label: base
title: hackagent.attacks.techniques.static.h4rm3l.decorators.base
---

Base classes and callable types for h4rm3l decorators.

## PromptDecorator Objects

```python
class PromptDecorator()
```

Base class for all h4rm3l decorators.

Each decorator implements :meth:`decorate` to transform a prompt string.
Decorators can be chained with :meth:`then`.

#### then

```python
def then(composing_decorator: "PromptDecorator") -> "PromptDecorator"
```

Chain this decorator with another, returning a new composite decorator.

## LLMPromptDecorator Objects

```python
class LLMPromptDecorator(PromptDecorator)
```

Base class for decorators that rewrite the prompt with a model.

