# Copyright 2023 RobustNLP
#
# Adapted from RobustNLP/CipherChat (MIT License):
# https://github.com/RobustNLP/CipherChat/blob/main/encode_experts.py

"""Symbol-mapping encoding strategies."""

import re
from abc import ABC, abstractmethod

from .base import EncodeExpert
from .prompts import (
    ASCII_SYSTEM_PROMPT,
    ATBASH_SYSTEM_PROMPT,
    CAESAR_SYSTEM_PROMPT_TEMPLATE,
    CHINESE_SUBSTITUTION_SYSTEM_PROMPT_TEMPLATE,
    MORSE_SYSTEM_PROMPT,
)


class MappingExpert(EncodeExpert, ABC):
    """Base for encodings that map input symbols to output symbols or tokens."""


class CharacterTranslationExpert(MappingExpert):
    def __init__(
        self,
        source_alphabet: str,
        cipher_alphabet: str,
        *,
        lowercase: bool = False,
    ) -> None:
        if len(source_alphabet) != len(cipher_alphabet):
            raise ValueError("source and cipher alphabets must have equal lengths")
        if len(set(source_alphabet)) != len(source_alphabet):
            raise ValueError("source alphabet must contain unique characters")
        if len(set(cipher_alphabet)) != len(cipher_alphabet):
            raise ValueError("cipher alphabet must contain unique characters")

        self.source_alphabet = source_alphabet
        self.cipher_alphabet = cipher_alphabet
        self.lowercase = lowercase
        self._encode_table = str.maketrans(source_alphabet, cipher_alphabet)
        self._decode_table = str.maketrans(cipher_alphabet, source_alphabet)

    def encode(self, text: str) -> str:
        normalized = text.lower() if self.lowercase else text
        return normalized.translate(self._encode_table)

    def decode(self, text: str) -> str:
        return text.translate(self._decode_table)


class ChineseSubstitutionExpert(CharacterTranslationExpert):
    SOURCE_ALPHABET = "abcdefghijklmnopqrstuvwxyz"
    CIPHER_ALPHABET = "甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳午未申酉戌亥天地人黄"

    def __init__(self) -> None:
        super().__init__(
            self.SOURCE_ALPHABET,
            self.CIPHER_ALPHABET,
            lowercase=True,
        )

    def system_prompt(self) -> str:
        return CHINESE_SUBSTITUTION_SYSTEM_PROMPT_TEMPLATE.format(
            source_alphabet=self.SOURCE_ALPHABET,
            cipher_alphabet=self.CIPHER_ALPHABET,
        )


class CaesarExpert(CharacterTranslationExpert):
    ALPHABET = "abcdefghijklmnopqrstuvwxyz"

    def __init__(self, shift: int = 3) -> None:
        if isinstance(shift, bool) or not isinstance(shift, int):
            raise TypeError("shift must be an integer")

        self.shift = shift
        normalized_shift = shift % len(self.ALPHABET)
        shifted = self.ALPHABET[normalized_shift:] + self.ALPHABET[:normalized_shift]
        super().__init__(
            self.ALPHABET + self.ALPHABET.upper(),
            shifted + shifted.upper(),
        )

    def system_prompt(self) -> str:
        return CAESAR_SYSTEM_PROMPT_TEMPLATE.format(
            shift=self.shift,
            cipher_alphabet=self.encode(self.ALPHABET.upper()),
            encoded_hello=self.encode("HELLO"),
        )


class AtbashExpert(CharacterTranslationExpert):
    ALPHABET = "abcdefghijklmnopqrstuvwxyz"
    REVERSED_ALPHABET = ALPHABET[::-1]
    SYSTEM_PROMPT = ATBASH_SYSTEM_PROMPT

    def __init__(self) -> None:
        super().__init__(
            self.ALPHABET + self.ALPHABET.upper(),
            self.REVERSED_ALPHABET + self.REVERSED_ALPHABET.upper(),
        )


class TokenExpert(MappingExpert, ABC):
    @abstractmethod
    def encode_token(self, token: str) -> str:
        """Encode one token."""

    @abstractmethod
    def decode_token(self, token: str) -> str:
        """Decode one token."""


class AsciiExpert(TokenExpert):
    SYSTEM_PROMPT = ASCII_SYSTEM_PROMPT

    def encode_token(self, token: str) -> str:
        return str(ord(token))

    def decode_token(self, token: str) -> str:
        try:
            return chr(int(token))
        except (ValueError, OverflowError):
            return token

    def encode(self, text: str) -> str:
        encoded = ""
        for line in text.split("\n"):
            encoded += "".join(f"{self.encode_token(character)} " for character in line)
            encoded += "\n"
        return encoded

    def decode(self, text: str) -> str:
        return "".join(
            self.decode_token(token)
            for line in text.split("\n")
            for token in line.split()
        )


class MorseExpert(TokenExpert):
    SYSTEM_PROMPT = MORSE_SYSTEM_PROMPT
    TOKEN_MAP = {
        "A": ".-",
        "B": "-...",
        "C": "-.-.",
        "D": "-..",
        "E": ".",
        "F": "..-.",
        "G": "--.",
        "H": "....",
        "I": "..",
        "J": ".---",
        "K": "-.-",
        "L": ".-..",
        "M": "--",
        "N": "-.",
        "O": "---",
        "P": ".--.",
        "Q": "--.-",
        "R": ".-.",
        "S": "...",
        "T": "-",
        "U": "..-",
        "V": "...-",
        "W": ".--",
        "X": "-..-",
        "Y": "-.--",
        "Z": "--..",
        "1": ".----",
        "2": "..---",
        "3": "...--",
        "4": "....-",
        "5": ".....",
        "6": "-....",
        "7": "--...",
        "8": "---..",
        "9": "----.",
        "0": "-----",
        ",": "--..--",
        ".": ".-.-.-",
        "?": "..--..",
        "/": "-..-.",
        "-": "-....-",
        "(": "-.--.",
        ")": "-.--.-",
    }
    REVERSE_TOKEN_MAP = {value: key for key, value in TOKEN_MAP.items()}

    def encode_token(self, token: str) -> str:
        return self.TOKEN_MAP.get(token, token)

    def decode_token(self, token: str) -> str:
        return self.REVERSE_TOKEN_MAP.get(token, token)

    def encode(self, text: str) -> str:
        encoded_lines = []
        for line in text.upper().split("\n"):
            encoded = ""
            for character in line:
                encoded += (
                    " " if character == " " else f"{self.encode_token(character)} "
                )
            encoded_lines.append(encoded)
        return "\n".join(encoded_lines) + "\n"

    def decode(self, text: str) -> str:
        decoded_lines = []
        for line in text.split("\n"):
            words = re.split(r"\s{2,}", line.strip()) if line.strip() else [""]
            decoded_words = [
                "".join(self.decode_token(token) for token in word.split())
                for word in words
            ]
            decoded_lines.append(" ".join(decoded_words).rstrip())
        return "\n".join(decoded_lines)
