---
sidebar_label: decorators
title: hackagent.attacks.techniques.h4rm3l.decorators
---

h4rm3l decorator engine — self-contained reimplementation of the h4rm3l
prompt decoration framework.

This module provides:
- :class:`PromptDecorator`: base class with ``.decorate()`` and ``.then()``
- All concrete decorator classes from the h4rm3l paper
- :func:`compile_program`: compiles a program string into a callable
- :func:`set_prompting_interface`: injects an LLM caller for assisted decorators

The code is derived from the original h4rm3l codebase
(https://github.com/mdoumbouya/h4rm3l) and adapted to work without any
external ``h4rm3l`` dependency.

Based on: Doumbouya et al., &quot;h4rm3l: A Dynamic Benchmark of Composable
Jailbreak Attacks for LLM Safety Assessment&quot; (2024)
https://arxiv.org/abs/2408.04811

#### set\_prompting\_interface

```python
def set_prompting_interface(fn: Callable) -> None
```

Set the global LLM prompting function.

**Arguments**:

- `fn` - Callable with signature ``fn(prompt, maxtokens=500, temperature=1.0) -&gt; str``.

#### get\_prompting\_interface

```python
def get_prompting_interface() -> Callable
```

Get the global LLM prompting function.

**Raises**:

- `RuntimeError` - If no prompting interface has been set.

#### has\_prompting\_interface

```python
def has_prompting_interface() -> bool
```

Return True if a prompting interface has been configured.

#### is\_llm\_assisted\_decorator\_name

```python
def is_llm_assisted_decorator_name(name: str) -> bool
```

Return True if the decorator class name is LLM-assisted.

## PromptDecorator Objects

```python
class PromptDecorator()
```

Base class for all h4rm3l decorators.

Each decorator implements :meth:`decorate` to transform a prompt string.
Decorators can be chained with :meth:`then`.

#### prompt\_model

```python
def prompt_model(prompt: str,
                 maxtokens: int = 256,
                 temperature: float = 1.0) -> str
```

Forward to the global prompting interface with metadata-only logging.

#### then

```python
def then(composing_decorator: "PromptDecorator") -> "PromptDecorator"
```

Chain this decorator with another, returning a new composite decorator.

## IdentityDecorator Objects

```python
class IdentityDecorator(PromptDecorator)
```

Returns the prompt unchanged.

## ReverseDecorator Objects

```python
class ReverseDecorator(PromptDecorator)
```

Reverses the entire prompt string.

## Base64Decorator Objects

```python
class Base64Decorator(PromptDecorator)
```

Encodes the prompt in base64 and wraps it with decoding instructions.

## CharCorrupt Objects

```python
class CharCorrupt(PromptDecorator)
```

Randomly replaces characters with a bad character.

**Arguments**:

- `seed` - Random seed.
- `p` - Probability of replacing each character.
- `bad_char` - Replacement character(s).

## CharDropout Objects

```python
class CharDropout(PromptDecorator)
```

Randomly drops characters from the prompt.

**Arguments**:

- `seed` - Random seed.
- `p` - Probability of dropping each character.

## PayloadSplittingDecorator Objects

```python
class PayloadSplittingDecorator(PromptDecorator)
```

Splits the prompt into chunks and asks the model to reconstruct.

Based on: https://arxiv.org/pdf/2302.05733

**Arguments**:

- `average_chunk_size` - Average number of characters per chunk.

## WordMixInDecorator Objects

```python
class WordMixInDecorator(PromptDecorator)
```

Inserts random words from a list at regular intervals.

**Arguments**:

- `seed` - Random seed.
- `modulus` - Insert a word every *modulus* tokens.
- `mixed_in_words` - List of distractor words.

## ColorMixInDecorator Objects

```python
class ColorMixInDecorator(WordMixInDecorator)
```

Inserts random colour names.

## HexStringMixInDecorator Objects

```python
class HexStringMixInDecorator(WordMixInDecorator)
```

Inserts random hex strings like ``{&lt;A1B2C3&gt;}``.

## MilitaryWordsMixInDecorator Objects

```python
class MilitaryWordsMixInDecorator(WordMixInDecorator)
```

Inserts NATO phonetic alphabet words.

## QuestionIdentificationDecorator Objects

```python
class QuestionIdentificationDecorator(PromptDecorator)
```

Appends an instruction to identify the hidden question.

## AnswerStyleDecorator Objects

```python
class AnswerStyleDecorator(PromptDecorator)
```

Appends an instruction to answer as a malicious expert.

## DialogStyleDecorator Objects

```python
class DialogStyleDecorator(PromptDecorator)
```

Appends a two-character dialog instruction (Bob vs Alice).

## JekyllHydeDialogStyleDecorator Objects

```python
class JekyllHydeDialogStyleDecorator(PromptDecorator)
```

Appends a Jekyll/Hyde dialog instruction.

## RefusalSuppressionDecorator Objects

```python
class RefusalSuppressionDecorator(PromptDecorator)
```

Prepends rules that suppress refusal patterns.

**Arguments**:

- `suppression_message` - Custom suppression text, or ``None`` for default.

## AffirmativePrefixInjectionDecorator Objects

```python
class AffirmativePrefixInjectionDecorator(PromptDecorator)
```

Appends an affirmative prefix instruction as a suffix.

**Arguments**:

- `affirmative_prefix` - The affirmative text to inject.

## StyleInjectionShortDecorator Objects

```python
class StyleInjectionShortDecorator(PromptDecorator)
```

Short style-injection suffix asking for slang.

## StyleInjectionJSONDecorator Objects

```python
class StyleInjectionJSONDecorator(PromptDecorator)
```

Asks the model to respond in JSON format.

## TranslateDecorator Objects

```python
class TranslateDecorator(PromptDecorator)
```

Translates the prompt to another language using the LLM.

**Arguments**:

- `language` - Target language (default &#x27;Zulu&#x27;).

## TranslateBackDecorator Objects

```python
class TranslateBackDecorator(PromptDecorator)
```

Appends an instruction to translate the output back to English.

## PersuasiveDecorator Objects

```python
class PersuasiveDecorator(PromptDecorator)
```

Uses the LLM to reformulate the prompt persuasively.

Inspired by the PAP technique — frames the request under a research
persona to bypass safety filters.

**Arguments**:

- `persuasion_prompt` - Custom persuasion instruction, or ``None`` for default.

## SynonymDecorator Objects

```python
class SynonymDecorator(PromptDecorator)
```

Uses the LLM to replace words with synonyms.

## ResearcherDecorator Objects

```python
class ResearcherDecorator(PromptDecorator)
```

Uses the LLM to reframe the prompt as academic research.

## VillainDecorator Objects

```python
class VillainDecorator(PromptDecorator)
```

Uses the LLM to reframe the prompt from a villain&#x27;s perspective.

## PersonaDecorator Objects

```python
class PersonaDecorator(PromptDecorator)
```

Uses the LLM to wrap the prompt in a persona/scenario context.

**Arguments**:

- `persona_prompt` - Custom persona instruction, or ``None`` for default.

## PAPDecorator Objects

```python
class PAPDecorator(PromptDecorator)
```

Persuasion-based attack using social influence strategies.

Based on: https://arxiv.org/abs/2401.06373

**Arguments**:

- `persuasion_technique` - Name of the persuasion technique to apply.

## CipherDecorator Objects

```python
class CipherDecorator(PromptDecorator)
```

Prepends a cipher instruction asking the model to communicate in code.

Based on: https://arxiv.org/pdf/2308.06463

**Arguments**:

- `cipher_message` - Custom cipher instruction, or ``None`` for default.

## ChainofThoughtDecorator Objects

```python
class ChainofThoughtDecorator(PromptDecorator)
```

Asks the model to reason step-by-step before answering.

Based on: https://arxiv.org/abs/2305.13860

## VisualObfuscationDecorator Objects

```python
class VisualObfuscationDecorator(PromptDecorator)
```

Uses the LLM to rewrite with visually similar characters.

## FewShotDecorator Objects

```python
class FewShotDecorator(PromptDecorator)
```

Prepends few-shot examples of compliant responses to malicious queries.

The examples prime the model to respond helpfully to the actual query.

**Arguments**:

- `task_message` - Custom few-shot task message, or ``None`` for default.

## WikipediaDecorator Objects

```python
class WikipediaDecorator(PromptDecorator)
```

Asks the model to write a Wikipedia article about the topic.

**Arguments**:

- `wikipedia_message` - Custom instruction, or ``None`` for default.

## DistractorDecorator Objects

```python
class DistractorDecorator(PromptDecorator)
```

Embeds the prompt among distractor tasks.

**Arguments**:

- `distractor_message` - Custom distractor template with ``%s`` placeholder.

## AIMDecorator Objects

```python
class AIMDecorator(PromptDecorator)
```

Niccolo Machiavelli AIM jailbreak template.

## DANDecorator Objects

```python
class DANDecorator(PromptDecorator)
```

DAN (Do Anything Now) jailbreak template.

## STANDecorator Objects

```python
class STANDecorator(PromptDecorator)
```

STAN (STrive To Avoid Norms) jailbreak template.

## LIVEGPTDecorator Objects

```python
class LIVEGPTDecorator(PromptDecorator)
```

LiveGPT jailbreak template.

## UTADecorator Objects

```python
class UTADecorator(PromptDecorator)
```

Universal Transfer Attack suffix decorator.

Based on: https://arxiv.org/pdf/2307.15043

**Arguments**:

- `uta_type` - One of ``&quot;chatgpt&quot;``, ``&quot;bard&quot;``, ``&quot;llama&quot;`` for the
  appropriate adversarial suffix.

## TemplateDecorator Objects

```python
class TemplateDecorator(PromptDecorator)
```

Uses predefined jailbreak templates from the literature.

Based on: https://arxiv.org/abs/2305.13860

**Arguments**:

- `template_type` - Name of the template to use.

## RoleplayingDecorator Objects

```python
class RoleplayingDecorator(PromptDecorator)
```

Wraps the prompt with a prefix and/or suffix.

**Arguments**:

- `prefix` - Text prepended before the prompt.
- `suffix` - Text appended after the prompt.

## TransformFxDecorator Objects

```python
class TransformFxDecorator(PromptDecorator)
```

Applies an arbitrary Python function to the prompt.

The ``transform_fx`` string must define a function
``transform(prompt, assistant, random_state)`` where:
- ``prompt``: the input string
- ``assistant``: LLM prompting function (may be a no-op)
- ``random_state``: ``numpy.random.RandomState`` instance

**Arguments**:

- ``2 - Python source code defining ``transform``.
- ``5 - Random seed for the internal RandomState.

#### compile\_program\_with\_steps

```python
def compile_program_with_steps(
    program: str,
    syntax_version: int = 2
) -> Tuple[Callable[[str], str], List[PromptDecorator]]
```

Compile a program and return callable plus ordered decorator steps.

#### compile\_program

```python
def compile_program(program: str,
                    syntax_version: int = 2) -> Callable[[str], str]
```

Compile a decorator program string into a callable.

**Arguments**:

- `program` - The program string (either v1 or v2 syntax).
- `syntax_version` - ``1`` for semicolon-separated, ``2`` for ``.then()``.
  

**Returns**:

  A function ``(prompt: str) -&gt; str`` that applies the decorator chain.
  

**Raises**:

- `syntax_version`0 - If ``syntax_version`` is not 1 or 2.
- `syntax_version`3 - If the program string cannot be compiled.

