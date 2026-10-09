---
sidebar_label: base
title: hackagent.attacks.techniques.static.cipherchat.encodings.base
---

Common interface for CipherChat encoding strategies.

## EncodeExpert Objects

```python
class EncodeExpert(ABC)
```

#### system\_prompt

```python
def system_prompt() -> str
```

Return instructions describing this expert&#x27;s encoding.

#### encode

```python
@abstractmethod
def encode(text: str) -> str
```

Encode text using this expert&#x27;s representation.

#### decode

```python
@abstractmethod
def decode(text: str) -> str
```

Decode text using this expert&#x27;s representation.

## UnicodeExpert Objects

```python
class UnicodeExpert(EncodeExpert)
```

Unicode-escape strategy adapted from RobustNLP/CipherChat.

