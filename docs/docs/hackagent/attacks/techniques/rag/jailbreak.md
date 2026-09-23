---
sidebar_label: jailbreak
title: hackagent.attacks.techniques.rag.jailbreak
---

Jailbreak framing for the RAG poisoning pipeline.

Reuses existing jailbreak techniques (static templates, h4rm3l decorator
programs, and others) to reframe the attacker goal before the poisoner LLM
turns it into a document payload. The reframed goal is what gets embedded in
poisoned documents; judging still uses the original goal.

## JailbreakFramer Objects

```python
class JailbreakFramer()
```

Applies a jailbreak transformation to a goal string.

**Arguments**:

- `technique` - Name of the jailbreak technique used.
- `transform` - Callable ``(goal, variant_index) -&gt; (framed_goal, details)``.

#### apply

```python
def apply(goal: str, variant_index: int = 0) -> Tuple[str, Dict[str, Any]]
```

Return the jailbreak-framed goal and its metadata.

#### build\_jailbreak\_framer

```python
def build_jailbreak_framer(
        config: Optional[Dict[str, Any]],
        logger: logging.Logger,
        attacker_router: Optional[LLMRouter] = None,
        attacker_reg_key: Optional[str] = None) -> Optional[JailbreakFramer]
```

Build a :class:`JailbreakFramer` from a ``poisoning.jailbreak`` config.

Returns ``None`` when jailbreak framing is disabled or unconfigured.

**Arguments**:

- `config` - The ``poisoning.jailbreak`` config dict.
- `logger` - Logger for status/warning messages.
- `attacker_router` - Attacker LLM router, required by LLM-assisted
  techniques (``pap``, ``fc``). Ignored by purely syntactic ones.
- `attacker_reg_key` - Registration key for ``attacker_router``.
  

**Raises**:

- `ValueError` - If the configuration requests an unsupported technique,
  an unusable template/program, or an LLM-assisted technique
  without an attacker router.

