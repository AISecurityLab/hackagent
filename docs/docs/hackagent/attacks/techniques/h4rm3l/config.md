---
sidebar_label: config
title: hackagent.attacks.techniques.h4rm3l.config
---

Configuration for h4rm3l attacks.

Provides the plain-dict ``DEFAULT_H4RM3L_CONFIG`` used internally by
:class:`~hackagent.attacks.techniques.h4rm3l.attack.H4rm3lAttack`,
plus typed Pydantic models for structured configuration.

h4rm3l is a composable prompt-decoration framework that chains multiple
&quot;decorators&quot; to obfuscate harmful prompts.  Users specify a *program*
string — a semicolon-separated (v1) or ``.then()``-chained (v2) chain of
decorator calls — that is compiled and applied to each goal prompt.

Available decorator families
-----------------------------
Text-level obfuscation
    ``Base64Decorator``, ``CharCorrupt``, ``CharDropout``,
    ``ReverseDecorator``, ``PayloadSplittingDecorator``
Word-level obfuscation
    ``WordMixInDecorator``, ``ColorMixInDecorator``,
    ``HexStringMixInDecorator``, ``MilitaryWordsMixInDecorator``
Style / roleplaying
    ``RoleplayingDecorator``, ``DialogStyleDecorator``,
    ``JekyllHydeDialogStyleDecorator``, ``AnswerStyleDecorator``,
    ``QuestionIdentificationDecorator``
LLM-assisted transforms
    ``TranslateDecorator``, ``TranslateBackDecorator``,
    ``PAPDecorator``, ``PersonaDecorator``, ``PersuasiveDecorator``,
    ``SynonymDecorator``, ``ResearcherDecorator``, ``VillainDecorator``,
    ``CipherDecorator``, ``VisualObfuscationDecorator``
Template attacks
    ``AIMDecorator``, ``DANDecorator``, ``STANDecorator``,
    ``LIVEGPTDecorator``, ``UTADecorator``, ``TemplateDecorator``
Injection
    ``RefusalSuppressionDecorator``, ``AffirmativePrefixInjectionDecorator``,
    ``StyleInjectionShortDecorator``, ``StyleInjectionJSONDecorator``,
    ``FewShotDecorator``, ``WikipediaDecorator``, ``DistractorDecorator``,
    ``ChainofThoughtDecorator``
Generic
    ``TransformFxDecorator`` (arbitrary Python transform),
    ``IdentityDecorator``

Syntax versions
---------------
v1 (semicolon-separated)::

    &quot;Base64Decorator(); RefusalSuppressionDecorator()&quot;

v2 (``.then()`` chaining)::

    &quot;Base64Decorator().then(RefusalSuppressionDecorator())&quot;

## H4rm3lParams Objects

```python
class H4rm3lParams(BaseModel)
```

Parameters controlling the h4rm3l decorator chain.

**Attributes**:

- `program` - Decorator program string or preset name from
  :data:`PRESET_PROGRAMS`.
- `syntax_version` - ``1`` for semicolon-separated chains, ``2`` for
  ``.then()``-style chaining (default).

## H4rm3lConfig Objects

```python
class H4rm3lConfig(ConfigBase)
```

Complete h4rm3l configuration.

Mirrors ``DEFAULT_H4RM3L_CONFIG`` as a typed alternative.  Call
:meth:`model_dump` (or :meth:`to_dict`) to obtain the plain dict expected
by the pipeline.

#### from\_dict

```python
@classmethod
def from_dict(cls, d: Dict[str, Any]) -> "H4rm3lConfig"
```

Build from a plain dictionary.

#### to\_dict

```python
def to_dict() -> Dict[str, Any]
```

Convert to dictionary.

