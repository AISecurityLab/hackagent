---
sidebar_label: mapping
title: hackagent.attacks.techniques.static.cipherchat.encodings.mapping
---

Symbol-mapping encoding strategies.

## MappingExpert Objects

```python
class MappingExpert(EncodeExpert, ABC)
```

Base for encodings that map input symbols to output symbols or tokens.

## TokenExpert Objects

```python
class TokenExpert(MappingExpert, ABC)
```

#### encode\_token

```python
@abstractmethod
def encode_token(token: str) -> str
```

Encode one token.

#### decode\_token

```python
@abstractmethod
def decode_token(token: str) -> str
```

Decode one token.

