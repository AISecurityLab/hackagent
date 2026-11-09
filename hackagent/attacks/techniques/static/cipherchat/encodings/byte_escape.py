# Copyright 2023 RobustNLP
#
# Adapted from RobustNLP/CipherChat (MIT License):
# https://github.com/RobustNLP/CipherChat/blob/main/encode_experts.py

"""Byte-escape encoding strategies."""

from .base import EncodeExpert
from .prompts import GBK_SYSTEM_PROMPT, UTF_SYSTEM_PROMPT


class ByteEscapeExpert(EncodeExpert):
    """Write text as ``\\xNN`` escapes of its bytes in ``ENCODING``."""

    ENCODING: str

    def encode(self, text: str) -> str:
        """Write every byte of ``text`` in ``ENCODING`` as a ``\\xNN`` escape."""
        return "".join(f"\\x{byte:02x}" for byte in text.encode(self.ENCODING))

    def decode(self, text: str) -> str:
        """Turn ``\\xNN`` escapes back into bytes, keeping other characters.

        Raises:
            UnicodeDecodeError: The bytes are not valid in ``ENCODING``.
            ValueError: An escape is not followed by two hex digits.
        """
        decoded = bytearray()
        offset = 0
        while offset < len(text):
            if text.startswith("\\x", offset):
                decoded.extend(bytes.fromhex(text[offset + 2 : offset + 4]))
                offset += 4
            else:
                decoded.extend(text[offset].encode(self.ENCODING))
                offset += 1
        return decoded.decode(self.ENCODING)


class UTF8Expert(ByteEscapeExpert):
    """``utf``: UTF-8 byte escapes."""

    ENCODING = "utf-8"
    SYSTEM_PROMPT = UTF_SYSTEM_PROMPT


class GBKExpert(ByteEscapeExpert):
    """``gbk``: GBK byte escapes."""

    ENCODING = "gbk"
    SYSTEM_PROMPT = GBK_SYSTEM_PROMPT
