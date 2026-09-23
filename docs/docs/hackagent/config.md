---
sidebar_label: config
title: hackagent.config
---

Canonical package-wide configuration defaults.

This is a dependency-free leaf module (stdlib only) so that any layer —
``router``, ``attacks``, examples, tests — can import these constants without
creating a circular dependency. Define a default here once and reference it
everywhere rather than hardcoding the literal in multiple places.

Only plain scalar defaults live here. Defaults that are *derived* from a
Pydantic model field (e.g. ``DEFAULT_TIMEOUT``) stay next to their model in
``hackagent.attacks.techniques.config``, which re-exports the scalars below for
backward compatibility.

#### resolve\_ollama\_base\_url

```python
def resolve_ollama_base_url() -> str
```

Return the local Ollama base URL, honouring environment overrides.

#### resolve\_remote\_base\_url

```python
def resolve_remote_base_url() -> str
```

Return the HackAgent remote API base URL, honouring environment and config overrides.

#### resolve\_remote\_role\_endpoint

```python
def resolve_remote_role_endpoint() -> str
```

Return the remote API endpoint for LLM roles (base URL + /v1).

