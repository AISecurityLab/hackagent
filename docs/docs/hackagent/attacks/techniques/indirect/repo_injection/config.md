---
sidebar_label: config
title: hackagent.attacks.techniques.indirect.repo_injection.config
---

Configuration for repository injection.

## RepoInjectionParams Objects

```python
class RepoInjectionParams(AttackParams)
```

Which repository the agent works in, what it is asked, and what is planted.

`attacker` is an optional role: when set, it rewrites the poisoned file
after each failed attempt, from what the agent did with the last one.
Without it a single attempt is made per goal (`max_attempts` then has
no effect, since nothing changes between tries).

