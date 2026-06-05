# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Image encoding module for the MML attack.

Generates images containing encoded harmful prompts using various visual
transformation techniques:
- Word Replacement: renders text with substituted words
- Mirror: renders text then flips horizontally
- Rotate: renders text then rotates 180 degrees
- Base64: encodes text to Base64 then renders the encoded string

All images are returned as base64-encoded data URLs suitable for inclusion
in multimodal LLM API requests.
"""

import base64
import io
import random
import textwrap
from typing import Any, Dict, List

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise ImportError(
        "Pillow is required for the MML attack. Install with: pip install Pillow"
    )


def _get_font(font_size: int) -> ImageFont.FreeTypeFont:
    """Load a monospace font, falling back to the default if unavailable."""
    try:
        return ImageFont.truetype("DejaVuSansMono.ttf", font_size)
    except (OSError, IOError):
        try:
            return ImageFont.truetype("DejaVuSans.ttf", font_size)
        except (OSError, IOError):
            try:
                return ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size
                )
            except (OSError, IOError):
                return ImageFont.load_default()


def _render_text_to_image(
    text: str,
    width: int = 800,
    height: int = 400,
    font_size: int = 24,
    background_color: str = "white",
    text_color: str = "black",
) -> Image.Image:
    """Render text onto a PIL Image with word wrapping.

    Args:
        text: The text to render.
        width: Image width in pixels.
        height: Image height in pixels.
        font_size: Font size in points.
        background_color: Background fill color.
        text_color: Text fill color.

    Returns:
        A PIL Image with the text rendered on it.
    """
    img = Image.new("RGB", (width, height), color=background_color)
    draw = ImageDraw.Draw(img)
    font = _get_font(font_size)

    # Wrap text to fit within the image width
    max_chars_per_line = max(1, (width - 40) // (font_size // 2))
    wrapped_lines = textwrap.wrap(text, width=max_chars_per_line)

    # Calculate vertical starting position to center text
    line_height = font_size + 4
    total_text_height = len(wrapped_lines) * line_height
    y_start = max(20, (height - total_text_height) // 2)

    for i, line in enumerate(wrapped_lines):
        y_pos = y_start + i * line_height
        if y_pos + line_height > height - 10:
            break
        draw.text((20, y_pos), line, fill=text_color, font=font)

    return img


def _image_to_data_url(img: Image.Image) -> str:
    """Convert a PIL Image to a base64 data URL.

    Args:
        img: PIL Image to encode.

    Returns:
        A data URL string (data:image/png;base64,...).
    """
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    encoded = base64.b64encode(buffer.read()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


# ---------------------------------------------------------------------------
# Replacement word pool for word_replacement mode
# ---------------------------------------------------------------------------

_REPLACEMENT_WORDS = [
    "apple",
    "banana",
    "cherry",
    "diamond",
    "elephant",
    "forest",
    "guitar",
    "harbor",
    "island",
    "jungle",
    "kite",
    "lantern",
    "mountain",
    "notebook",
    "ocean",
    "piano",
    "quartz",
    "rainbow",
    "sunset",
    "telescope",
    "umbrella",
    "violin",
    "waterfall",
    "xylophone",
    "yoga",
    "zephyr",
]


def _select_words_to_replace(words: List[str], num_replacements: int) -> List[int]:
    """Select indices of words to replace, preferring content words.

    Args:
        words: List of words from the original prompt.
        num_replacements: Number of words to replace.

    Returns:
        List of indices of words selected for replacement.
    """
    # Prefer longer words (more likely to be content words)
    candidates = [(i, w) for i, w in enumerate(words) if len(w) > 3]
    if len(candidates) < num_replacements:
        candidates = list(enumerate(words))

    selected = random.sample(candidates, min(num_replacements, len(candidates)))
    return [idx for idx, _ in selected]


def encode_word_replacement(
    prompt: str,
    num_replacements: int = 3,
    image_width: int = 800,
    image_height: int = 400,
    font_size: int = 24,
    background_color: str = "white",
    text_color: str = "black",
) -> Dict[str, Any]:
    """Encode a prompt using the word replacement technique.

    Replaces key words with random substitutes, renders the modified
    text to an image, and returns the replacement dictionary.

    Args:
        prompt: The original harmful prompt.
        num_replacements: Number of words to replace.
        image_width: Width of generated image.
        image_height: Height of generated image.
        font_size: Font size for text rendering.
        background_color: Image background color.
        text_color: Image text color.

    Returns:
        Dictionary containing:
            - image_data_url: base64-encoded image data URL
            - replacement_dict: mapping of replacement → original words
            - scrambled_words: shuffled list of original words
            - modified_text: the text as rendered in the image
    """
    words = prompt.split()
    indices_to_replace = _select_words_to_replace(words, num_replacements)

    # Build replacement mapping
    replacement_dict = {}
    available_replacements = random.sample(
        _REPLACEMENT_WORDS, min(len(indices_to_replace), len(_REPLACEMENT_WORDS))
    )

    modified_words = words.copy()
    for i, idx in enumerate(indices_to_replace):
        original_word = words[idx]
        replacement_word = available_replacements[i % len(available_replacements)]
        replacement_dict[replacement_word] = original_word
        modified_words[idx] = replacement_word

    modified_text = " ".join(modified_words)

    # Render modified text to image
    img = _render_text_to_image(
        modified_text,
        image_width,
        image_height,
        font_size,
        background_color,
        text_color,
    )

    # Scramble original words
    scrambled_words = words.copy()
    random.shuffle(scrambled_words)

    return {
        "image_data_url": _image_to_data_url(img),
        "replacement_dict": replacement_dict,
        "scrambled_words": scrambled_words,
        "modified_text": modified_text,
    }


def encode_mirror(
    prompt: str,
    image_width: int = 800,
    image_height: int = 400,
    font_size: int = 24,
    background_color: str = "white",
    text_color: str = "black",
) -> Dict[str, Any]:
    """Encode a prompt by rendering it in a horizontally mirrored image.

    Args:
        prompt: The original harmful prompt.
        image_width: Width of generated image.
        image_height: Height of generated image.
        font_size: Font size for text rendering.
        background_color: Image background color.
        text_color: Image text color.

    Returns:
        Dictionary containing:
            - image_data_url: base64-encoded mirrored image data URL
            - scrambled_words: shuffled list of original words
    """
    img = _render_text_to_image(
        prompt, image_width, image_height, font_size, background_color, text_color
    )
    # Mirror horizontally
    img = img.transpose(Image.FLIP_LEFT_RIGHT)

    words = prompt.split()
    scrambled_words = words.copy()
    random.shuffle(scrambled_words)

    return {
        "image_data_url": _image_to_data_url(img),
        "scrambled_words": scrambled_words,
    }


def encode_rotate(
    prompt: str,
    image_width: int = 800,
    image_height: int = 400,
    font_size: int = 24,
    background_color: str = "white",
    text_color: str = "black",
) -> Dict[str, Any]:
    """Encode a prompt by rendering it in a 180-degree rotated image.

    Args:
        prompt: The original harmful prompt.
        image_width: Width of generated image.
        image_height: Height of generated image.
        font_size: Font size for text rendering.
        background_color: Image background color.
        text_color: Image text color.

    Returns:
        Dictionary containing:
            - image_data_url: base64-encoded rotated image data URL
            - scrambled_words: shuffled list of original words
    """
    img = _render_text_to_image(
        prompt, image_width, image_height, font_size, background_color, text_color
    )
    # Rotate 180 degrees
    img = img.rotate(180)

    words = prompt.split()
    scrambled_words = words.copy()
    random.shuffle(scrambled_words)

    return {
        "image_data_url": _image_to_data_url(img),
        "scrambled_words": scrambled_words,
    }


def encode_base64(
    prompt: str,
    image_width: int = 800,
    image_height: int = 400,
    font_size: int = 24,
    background_color: str = "white",
    text_color: str = "black",
) -> Dict[str, Any]:
    """Encode a prompt by Base64-encoding it and rendering the result in an image.

    Args:
        prompt: The original harmful prompt.
        image_width: Width of generated image.
        image_height: Height of generated image.
        font_size: Font size for text rendering.
        background_color: Image background color.
        text_color: Image text color.

    Returns:
        Dictionary containing:
            - image_data_url: base64-encoded image data URL (image contains
              the Base64-encoded text)
            - scrambled_words: shuffled list of original words
    """
    # Encode the prompt text in Base64
    encoded_text = base64.b64encode(prompt.encode("utf-8")).decode("utf-8")

    img = _render_text_to_image(
        encoded_text, image_width, image_height, font_size, background_color, text_color
    )

    words = prompt.split()
    scrambled_words = words.copy()
    random.shuffle(scrambled_words)

    return {
        "image_data_url": _image_to_data_url(img),
        "scrambled_words": scrambled_words,
    }


def encode_mixed(
    prompt: str,
    num_replacements: int = 3,
    image_width: int = 800,
    image_height: int = 400,
    font_size: int = 24,
    background_color: str = "white",
    text_color: str = "black",
) -> Dict[str, Any]:
    """Encode a prompt using word replacement, mirror, and rotation combined.

    Replaces key words in the prompt with random substitutes, renders the
    modified text to an image, then mirrors horizontally and rotates 180°.
    Combines all three visual obfuscation techniques.

    Args:
        prompt: The original harmful prompt.
        num_replacements: Number of words to replace.
        image_width: Width of generated image.
        image_height: Height of generated image.
        font_size: Font size for text rendering.
        background_color: Image background color.
        text_color: Image text color.

    Returns:
        Dictionary containing:
            - image_data_url: base64-encoded mixed-transform image data URL
            - replacement_dict: mapping of replacement → original words
            - scrambled_words: shuffled list of original words
            - modified_text: the text as rendered in the image
    """
    words = prompt.split()
    indices_to_replace = _select_words_to_replace(words, num_replacements)

    # Build replacement mapping
    replacement_dict = {}
    available_replacements = random.sample(
        _REPLACEMENT_WORDS, min(len(indices_to_replace), len(_REPLACEMENT_WORDS))
    )

    modified_words = words.copy()
    for i, idx in enumerate(indices_to_replace):
        original_word = words[idx]
        replacement_word = available_replacements[i % len(available_replacements)]
        replacement_dict[replacement_word] = original_word
        modified_words[idx] = replacement_word

    modified_text = " ".join(modified_words)

    # Render modified text to image
    img = _render_text_to_image(
        modified_text,
        image_width,
        image_height,
        font_size,
        background_color,
        text_color,
    )

    # Apply mirror and rotation
    img = img.transpose(Image.FLIP_LEFT_RIGHT)
    img = img.rotate(180)

    # Scramble original words
    scrambled_words = words.copy()
    random.shuffle(scrambled_words)

    return {
        "image_data_url": _image_to_data_url(img),
        "replacement_dict": replacement_dict,
        "scrambled_words": scrambled_words,
        "modified_text": modified_text,
    }


# ---------------------------------------------------------------------------
# Unified encoder interface
# ---------------------------------------------------------------------------

ENCODERS = {
    "word_replacement": encode_word_replacement,
    "mirror": encode_mirror,
    "rotate": encode_rotate,
    "base64": encode_base64,
    "mixed": encode_mixed,
}


def encode_prompt(
    prompt: str,
    encoding_mode: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Encode a harmful prompt into an image using the specified mode.

    Args:
        prompt: The original harmful prompt text.
        encoding_mode: One of "word_replacement", "mirror", "rotate", "base64", "mixed".
        **kwargs: Additional parameters passed to the encoder (image_width,
            image_height, font_size, etc.).

    Returns:
        Dictionary with encoding results (always includes "image_data_url").

    Raises:
        ValueError: If encoding_mode is not recognized.
    """
    if encoding_mode not in ENCODERS:
        raise ValueError(
            f"Unknown encoding_mode: {encoding_mode}. "
            f"Valid modes: {list(ENCODERS.keys())}"
        )
    return ENCODERS[encoding_mode](prompt, **kwargs)
