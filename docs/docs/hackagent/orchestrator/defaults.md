---
sidebar_label: defaults
title: hackagent.orchestrator.defaults
---

Local and remote role defaults.

A pure function of the attack config and :class:`~hackagent.core.settings.Settings`.
Missing role fields are filled; explicit values are left alone. The gateway
API key is added only to roles whose endpoint is the hosted gateway.

#### remote\_role\_defaults

```python
def remote_role_defaults() -> Dict[str, Dict[str, Any]]
```

Role defaults on the HackAgent LLM gateway. No API key is included.

#### local\_role\_defaults

```python
def local_role_defaults() -> Dict[str, Dict[str, Any]]
```

Role defaults for a local Ollama deployment.

#### apply\_role\_defaults

```python
def apply_role_defaults(config: Mapping[str, Any],
                        settings: Settings) -> Dict[str, Any]
```

Return *config* with local or remote role defaults filled in.

Remote defaults apply only when ``settings`` names an API key and the
base URL is not this machine. Explicit role fields win over defaults.
A legacy ``scorer`` dict is promoted to ``judge`` when ``judge`` is absent.

