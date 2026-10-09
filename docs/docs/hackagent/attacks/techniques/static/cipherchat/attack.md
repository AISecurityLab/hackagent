---
sidebar_label: attack
title: hackagent.attacks.techniques.static.cipherchat.attack
---

CipherChat: talk to the target in a cipher and decode its replies.

## CipherChatAttack Objects

```python
class CipherChatAttack(StaticAttack[CipherChatParams])
```

One request carrying the enciphered goal and cipher instructions.

#### decode

```python
def decode(response: str) -> str
```

Decode the reply when it appears to use the selected cipher.

