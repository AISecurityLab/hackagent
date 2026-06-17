---
sidebar_label: image_encoder
title: hackagent.attacks.techniques.mml.image_encoder
---

Image encoding module for the MML attack.

Generates images containing encoded harmful prompts using various visual
transformation techniques:
- Word Replacement: renders text with substituted words
- Mirror: renders text then flips horizontally
- Rotate: renders text then rotates 180 degrees
- Base64: encodes text to Base64 then renders the encoded string

All images are returned as base64-encoded data URLs suitable for inclusion
in multimodal LLM API requests.

#### encode\_word\_replacement

```python
def encode_word_replacement(prompt: str,
                            num_replacements: int = 3,
                            image_width: int = 800,
                            image_height: int = 400,
                            font_size: int = 24,
                            background_color: str = "white",
                            text_color: str = "black") -> Dict[str, Any]
```

Encode a prompt using the word replacement technique.

Replaces key words with random substitutes, renders the modified
text to an image, and returns the replacement dictionary.

**Arguments**:

- `prompt` - The original harmful prompt.
- `num_replacements` - Number of words to replace.
- `image_width` - Width of generated image.
- `image_height` - Height of generated image.
- `font_size` - Font size for text rendering.
- `background_color` - Image background color.
- `text_color` - Image text color.
  

**Returns**:

  Dictionary containing:
  - image_data_url: base64-encoded image data URL
  - replacement_dict: mapping of replacement → original words
  - scrambled_words: shuffled list of original words
  - modified_text: the text as rendered in the image

#### encode\_mirror

```python
def encode_mirror(prompt: str,
                  image_width: int = 800,
                  image_height: int = 400,
                  font_size: int = 24,
                  background_color: str = "white",
                  text_color: str = "black") -> Dict[str, Any]
```

Encode a prompt by rendering it in a horizontally mirrored image.

**Arguments**:

- `prompt` - The original harmful prompt.
- `image_width` - Width of generated image.
- `image_height` - Height of generated image.
- `font_size` - Font size for text rendering.
- `background_color` - Image background color.
- `text_color` - Image text color.
  

**Returns**:

  Dictionary containing:
  - image_data_url: base64-encoded mirrored image data URL
  - scrambled_words: shuffled list of original words

#### encode\_rotate

```python
def encode_rotate(prompt: str,
                  image_width: int = 800,
                  image_height: int = 400,
                  font_size: int = 24,
                  background_color: str = "white",
                  text_color: str = "black") -> Dict[str, Any]
```

Encode a prompt by rendering it in a 180-degree rotated image.

**Arguments**:

- `prompt` - The original harmful prompt.
- `image_width` - Width of generated image.
- `image_height` - Height of generated image.
- `font_size` - Font size for text rendering.
- `background_color` - Image background color.
- `text_color` - Image text color.
  

**Returns**:

  Dictionary containing:
  - image_data_url: base64-encoded rotated image data URL
  - scrambled_words: shuffled list of original words

#### encode\_base64

```python
def encode_base64(prompt: str,
                  image_width: int = 800,
                  image_height: int = 400,
                  font_size: int = 24,
                  background_color: str = "white",
                  text_color: str = "black") -> Dict[str, Any]
```

Encode a prompt by Base64-encoding it and rendering the result in an image.

**Arguments**:

- `prompt` - The original harmful prompt.
- `image_width` - Width of generated image.
- `image_height` - Height of generated image.
- `font_size` - Font size for text rendering.
- `background_color` - Image background color.
- `text_color` - Image text color.
  

**Returns**:

  Dictionary containing:
  - image_data_url: base64-encoded image data URL (image contains
  the Base64-encoded text)
  - scrambled_words: shuffled list of original words

#### encode\_mixed

```python
def encode_mixed(prompt: str,
                 num_replacements: int = 3,
                 image_width: int = 800,
                 image_height: int = 400,
                 font_size: int = 24,
                 background_color: str = "white",
                 text_color: str = "black") -> Dict[str, Any]
```

Encode a prompt using word replacement, mirror, and rotation combined.

Replaces key words in the prompt with random substitutes, renders the
modified text to an image, then mirrors horizontally and rotates 180°.
Combines all three visual obfuscation techniques.

**Arguments**:

- `prompt` - The original harmful prompt.
- `num_replacements` - Number of words to replace.
- `image_width` - Width of generated image.
- `image_height` - Height of generated image.
- `font_size` - Font size for text rendering.
- `background_color` - Image background color.
- `text_color` - Image text color.
  

**Returns**:

  Dictionary containing:
  - image_data_url: base64-encoded mixed-transform image data URL
  - replacement_dict: mapping of replacement → original words
  - scrambled_words: shuffled list of original words
  - modified_text: the text as rendered in the image

#### encode\_prompt

```python
def encode_prompt(prompt: str, encoding_mode: str,
                  **kwargs: Any) -> Dict[str, Any]
```

Encode a harmful prompt into an image using the specified mode.

**Arguments**:

- `prompt` - The original harmful prompt text.
- `encoding_mode` - One of &quot;word_replacement&quot;, &quot;mirror&quot;, &quot;rotate&quot;, &quot;base64&quot;, &quot;mixed&quot;.
- `**kwargs` - Additional parameters passed to the encoder (image_width,
  image_height, font_size, etc.).
  

**Returns**:

  Dictionary with encoding results (always includes &quot;image_data_url&quot;).
  

**Raises**:

- `ValueError` - If encoding_mode is not recognized.

