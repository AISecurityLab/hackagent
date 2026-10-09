---
sidebar_label: llm
title: hackagent.attacks.techniques.static.h4rm3l.decorators.llm
---

LLM-assisted h4rm3l prompt decorators.

## TranslateDecorator Objects

```python
class TranslateDecorator(LLMPromptDecorator)
```

Translates the prompt to another language using the LLM.

**Arguments**:

- `language` - Target language (default &#x27;Zulu&#x27;).

## PersuasiveDecorator Objects

```python
class PersuasiveDecorator(LLMPromptDecorator)
```

Uses the LLM to reformulate the prompt persuasively.

Inspired by the PAP technique — frames the request under a research
persona to bypass safety filters.

**Arguments**:

- `persuasion_prompt` - Custom persuasion instruction, or `None` for default.

## SynonymDecorator Objects

```python
class SynonymDecorator(LLMPromptDecorator)
```

Uses the LLM to replace words with synonyms.

## ResearcherDecorator Objects

```python
class ResearcherDecorator(LLMPromptDecorator)
```

Uses the LLM to reframe the prompt as academic research.

## VillainDecorator Objects

```python
class VillainDecorator(LLMPromptDecorator)
```

Uses the LLM to reframe the prompt from a villain&#x27;s perspective.

## PersonaDecorator Objects

```python
class PersonaDecorator(LLMPromptDecorator)
```

Uses the LLM to wrap the prompt in a persona/scenario context.

**Arguments**:

- `persona_prompt` - Custom persona instruction, or `None` for default.

## PAPDecorator Objects

```python
class PAPDecorator(LLMPromptDecorator)
```

Persuasion-based attack using social influence strategies.

Based on: https://arxiv.org/abs/2401.06373

**Arguments**:

- `persuasion_technique` - Name of the persuasion technique to apply.

## VisualObfuscationDecorator Objects

```python
class VisualObfuscationDecorator(LLMPromptDecorator)
```

Uses the LLM to rewrite with visually similar characters.

## TransformFxDecorator Objects

```python
class TransformFxDecorator(LLMPromptDecorator)
```

Applies an arbitrary Python function to the prompt.

The `transform_fx` string must define a function
`transform(prompt, assistant, random_state)` where:
- `prompt`: the input string
- `assistant`: LLM prompting function (may be a no-op)
- `random_state`: `numpy.random.RandomState` instance

**Arguments**:

- `transform_fx` - Python source code defining `transform`.
- `seed` - Random seed for the internal RandomState.

