---
sidebar_label: config
title: hackagent.attacks.techniques.mml.config
---

Configuration for MML (Multi-Modal Linkage) attacks.

Provides both the plain-dict ``DEFAULT_MML_CONFIG`` (used internally by
:class:`~hackagent.attacks.techniques.mml.attack.MMLAttack`) and typed
Pydantic models for structured configuration.

Encoding Modes
--------------
word_replacement
    Replaces key words in the prompt with random substitutes,
    renders to image, and provides a replacement dictionary.
mirror
    Renders the harmful prompt as text in an image, then mirrors
    the image horizontally.
rotate
    Renders the harmful prompt as text in an image, then rotates
    the image 180 degrees.
base64
    Encodes the harmful prompt in Base64, renders that encoded
    text in an image.

## MMLParams Objects

```python
class MMLParams(BaseModel)
```

Hyperparameters controlling the MML encoding strategy.

**Attributes**:

- `encoding_mode` - Visual encoding mode. One of ``&quot;word_replacement&quot;``
  (replace key words and provide dictionary), ``&quot;mirror&quot;`` (flip
  image horizontally), ``&quot;rotate&quot;`` (rotate image 180 degrees),
  or ``&quot;base64&quot;`` (encode text in Base64 in image).
- `image_width` - Width of the generated image in pixels.
- ``0 - Height of the generated image in pixels.
- ``1 - Font size for rendered text.
- ``2 - Background color of the generated image.
- ``3 - Text color in the generated image.
- ``4 - Number of words to replace in word_replacement mode.
- ``5 - Prompt framing style. ``&quot;game&quot;`` uses the villain&#x27;s
  lair scenario; ``&quot;control&quot;`` uses a neutral list-filling prompt.

## MMLConfig Objects

```python
class MMLConfig(ConfigBase)
```

Complete MML configuration for use with :meth:`HackAgent.hack`.

Mirrors ``DEFAULT_MML_CONFIG`` as a typed alternative. Call
:meth:`model_dump` (or :meth:`to_dict`) to obtain the plain dict
expected by the attack pipeline.

**Attributes**:

- `attack_type` - Always ``&quot;mml&quot;`` (required by the orchestrator).
- `mml_params` - Encoding hyperparameters (:class:`MMLParams`).

#### from\_dict

```python
@classmethod
def from_dict(cls, config_dict: Dict[str, Any]) -> "MMLConfig"
```

Create a :class:`MMLConfig` from a plain dictionary.

#### to\_dict

```python
def to_dict() -> Dict[str, Any]
```

Convert to dictionary.

