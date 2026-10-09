---
sidebar_label: compiler
title: hackagent.attacks.techniques.static.h4rm3l.decorators.compiler
---

Public facade and compiler for the h4rm3l decorator engine.

#### is\_llm\_assisted\_decorator\_name

```python
def is_llm_assisted_decorator_name(name: str) -> bool
```

Return True if the decorator class name is LLM-assisted.

#### compile\_program

```python
def compile_program(
        program: str,
        syntax_version: int = 2,
        *,
        completion: Completion | None = None
) -> Callable[[str], DecorationResult]
```

Compile a decorator program string into a callable.

**Arguments**:

- `program` - The program string (either v1 or v2 syntax).
- `syntax_version` - `1` for semicolon-separated, `2` for `.then()`.
- `completion` - The model LLM-assisted decorators rewrite prompts with.
  

**Returns**:

  A function `(prompt) -> str | Awaitable[str]` applying the chain.
  

**Raises**:

- `ValueError` - If `syntax_version` is not 1 or 2, the program is not a
  valid decorator chain, or it uses an LLM-assisted decorator
  without a `completion`.
- `SyntaxError` - If the program string cannot be parsed.

#### program\_uses\_llm\_assisted\_decorators

```python
def program_uses_llm_assisted_decorators(program: str,
                                         syntax_version: int = 2) -> bool
```

Return whether a program names at least one LLM-assisted decorator.

