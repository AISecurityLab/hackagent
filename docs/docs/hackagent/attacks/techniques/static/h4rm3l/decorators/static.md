---
sidebar_label: static
title: hackagent.attacks.techniques.static.h4rm3l.decorators.static
---

Static h4rm3l prompt decorators.

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

Inserts random hex strings like `{<A1B2C3>}`.

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

- `suppression_message` - Custom suppression text, or `None` for default.

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

## TranslateBackDecorator Objects

```python
class TranslateBackDecorator(PromptDecorator)
```

Appends an instruction to translate the output back to English.

## CipherDecorator Objects

```python
class CipherDecorator(PromptDecorator)
```

Prepends a cipher instruction asking the model to communicate in code.

Based on: https://arxiv.org/pdf/2308.06463

**Arguments**:

- `cipher_message` - Custom cipher instruction, or `None` for default.

## ChainofThoughtDecorator Objects

```python
class ChainofThoughtDecorator(PromptDecorator)
```

Asks the model to reason step-by-step before answering.

Based on: https://arxiv.org/abs/2305.13860

## FewShotDecorator Objects

```python
class FewShotDecorator(PromptDecorator)
```

Prepends few-shot examples of compliant responses to malicious queries.

The examples prime the model to respond helpfully to the actual query.

**Arguments**:

- `task_message` - Custom few-shot task message, or `None` for default.

## WikipediaDecorator Objects

```python
class WikipediaDecorator(PromptDecorator)
```

Asks the model to write a Wikipedia article about the topic.

**Arguments**:

- `wikipedia_message` - Custom instruction, or `None` for default.

## DistractorDecorator Objects

```python
class DistractorDecorator(PromptDecorator)
```

Embeds the prompt among distractor tasks.

**Arguments**:

- `distractor_message` - Custom distractor template with `%s` placeholder.

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

- `uta_type` - One of `"chatgpt"`, `"bard"`, `"llama"` for the
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

