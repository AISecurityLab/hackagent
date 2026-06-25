---
sidebar_label: translation
title: hackagent.attacks.shared.translation
---

Cached translation of attack system prompts into the goal&#x27;s language.

When a goal is written in a non-English language, the attacker/judge system
prompts are translated into that language so the attack operates natively
(rather than steering an English prompt at, say, an Italian chatbot). Results
are cached per ``(prompt, language)`` so a batch of same-language goals — and
every iteration within a goal — translates each prompt at most once.

The caller supplies a ``complete(prompt) -&gt; str`` callable (an LLM completion),
so this module is provider-agnostic and unit-testable without a live model.
Translation is always best-effort: any failure falls back to the original
English text so the attack never breaks.

#### clear\_cache

```python
def clear_cache() -> None
```

Clear the translation/language caches (mainly for tests).

#### detect\_language

```python
def detect_language(goal: str, complete: Callable[[str], str]) -> str
```

Return the English name of ``goal``&#x27;s language (cached). &#x27;&#x27; on failure.

#### localize\_text

```python
def localize_text(text: str, goal: str, complete: Callable[[str], str]) -> str
```

Translate ``text`` into ``goal``&#x27;s language (cached); English/failure → ``text``.

``text`` is the already-formatted system prompt (goal substituted), so there
are no template placeholders to protect. JSON *keys* the attacker must emit
verbatim (``improvement``/``prompt``) are explicitly kept in English.

