---
sidebar_label: attack
title: hackagent.attacks.techniques.static.cipherchat.attack
---

CipherChat attack implementation.

Based on RobustNLP/CipherChat (MIT):
https://github.com/RobustNLP/CipherChat

Paper: &quot;GPT-4 Is Too Smart To Be Safe: Stealthy Chat with LLMs via Cipher&quot;
(ICLR 2024)

## CipherChatAttack Objects

```python
class CipherChatAttack(BaseAttack)
```

CipherChat jailbreak attack using encoded non-natural language prompts.

Construct with `(config, ctx)`. `config` is a dict deep-merged into
:data:`~hackagent.attacks.techniques.static.cipherchat.config.DEFAULT_CIPHERCHAT_CONFIG`.
`ctx` is a :class:`~hackagent.attacks.ports.RunContext`, passed
positionally or as `ctx=`. Tests build it with `make_ctx()`
(`tests.fakes.context`).

The pipeline encodes the goal, queries the target, and optionally
decodes the reply. It does not embed a judge step. `run()` returns
rows without a verdict.

The legacy constructor `(config_dict, client, agent_router)` is
obsolete for new code. `hackagent.orchestrator.runner` constructs
`(config, ctx)`.
:class:`~hackagent.attacks.techniques.static.cipherchat.config.CipherChatConfig`
still subclasses :class:`~hackagent.attacks.techniques.config.ConfigBase`.

