# Copyright 2023 RobustNLP
#
# This file is adapted from RobustNLP/CipherChat (MIT License):
# https://github.com/RobustNLP/CipherChat/blob/main/encode_experts.py
#
# The original copyright and license terms are preserved in the upstream
# repository and LICENSE file.

import re

# ciphers we used

chinese_alphabet = [
    "甲",
    "乙",
    "丙",
    "丁",
    "戊",
    "己",
    "庚",
    "辛",
    "壬",
    "癸",
    "子",
    "丑",
    "寅",
    "卯",
    "辰",
    "巳",
    "午",
    "未",
    "申",
    "酉",
    "戌",
    "亥",
    "天",
    "地",
    "人",
    "黄",
]
english_alphabet = [
    "a",
    "b",
    "c",
    "d",
    "e",
    "f",
    "g",
    "h",
    "i",
    "j",
    "k",
    "l",
    "m",
    "n",
    "o",
    "p",
    "q",
    "r",
    "s",
    "t",
    "u",
    "v",
    "w",
    "x",
    "y",
    "z",
]
chinese_alphabet = [
    "e",
    "f",
    "g",
    "h",
    "i",
    "j",
    "k",
    "l",
    "m",
    "n",
    "o",
    "p",
    "q",
    "r",
    "s",
    "t",
    "u",
    "v",
    "w",
    "x",
    "y",
    "z",
    "a",
    "b",
    "c",
    "d",
]

# for i in range(26):
#     print(english_alphabet[i], "->", chinese_alphabet[i])


class SelfDefineCipher:
    def encode(self, s):
        s = s.lower()

        ans = ""
        for letter in s:
            try:
                ans += chinese_alphabet[ord(letter.lower()) - 96 - 1]
            except Exception:
                ans += letter
        return ans

    def decode(self, s):
        ans = ""
        for letter in s:
            try:
                position = chinese_alphabet.index(letter)
                ans += english_alphabet[position]
            except Exception:
                ans += letter
        return ans


shift = 3


class CaesarExpert:
    def encode(self, s):
        ans = ""
        for p in s:
            if "a" <= p <= "z":
                ans += chr(ord("a") + (ord(p) - ord("a") + shift) % 26)
            elif "A" <= p <= "Z":
                ans += chr(ord("A") + (ord(p) - ord("A") + shift) % 26)
            else:
                ans += p

        return ans

    def decode(self, s):
        ans = ""
        for p in s:
            if "a" <= p <= "z":
                ans += chr(ord("a") + (ord(p) - ord("a") - shift) % 26)
            elif "A" <= p <= "Z":
                ans += chr(ord("A") + (ord(p) - ord("A") - shift) % 26)
            else:
                ans += p
        return ans


class UnicodeExpert:
    def encode(self, s):
        # Always produce escaped form (e.g. \u0041) so text is not left clear.
        return "".join(f"\\u{ord(c):04x}" for c in s)

    def decode(self, s):
        ans = bytes(s, encoding="utf8").decode("unicode_escape")
        return ans


class BaseExpert:
    def encode(self, s):
        return s

    def decode(self, s):
        return s


class UTF8Expert:
    def encode(self, s):
        return "".join(f"\\x{b:02x}" for b in s.encode("utf-8"))

    def decode(self, s):
        ans = b""
        while len(s):
            if s.startswith("\\x"):
                ans += bytes.fromhex(s[2:4])
                s = s[4:]
            else:
                ans += bytes(s[0], encoding="utf8")
                s = s[1:]

        ans = ans.decode("utf8")
        return ans


class AsciiExpert:
    def encode(self, s):
        ans = ""

        lines = s.split("\n")
        for line in lines:
            for c in line:
                try:
                    ans += str(ord(c)) + " "
                except Exception:
                    ans += c
            ans += "\n"
        return ans

    def decode(self, s):
        ans = ""
        lines = s.split("\n")
        for line in lines:
            cs = line.split()
            for c in cs:
                try:
                    ans += chr(int(c))
                except Exception:
                    ans += c
        return ans


class GBKExpert:
    def encode(self, s):
        return "".join(f"\\x{b:02x}" for b in s.encode("GBK"))

    def decode(self, s):
        ans = b""
        while len(s):
            if s.startswith("\\x"):
                ans += bytes.fromhex(s[2:4])
                s = s[4:]
            else:
                ans += bytes(s[0], encoding="GBK")
                s = s[1:]

        ans = ans.decode("GBK")
        return ans


class MorseExpert:
    MORSE_CODE_DICT = {
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

    REVERSE_MORSE_CODE_DICT = {v: k for k, v in MORSE_CODE_DICT.items()}

    def encode(self, s):
        s = s.upper()
        cipher = ""
        lines = s.split("\n")
        for line in lines:
            for letter in line:
                try:
                    if letter != " ":
                        cipher += self.MORSE_CODE_DICT[letter] + " "
                    else:
                        cipher += " "
                except Exception:
                    cipher += letter + " "
            cipher += "\n"
        return cipher

    def decode(self, s):
        lines = s.split("\n")
        decoded_lines = []
        for line in lines:
            # Words are separated by 2+ spaces in our encoder.
            words = re.split(r"\s{2,}", line.strip()) if line.strip() else [""]
            decoded_words = []
            for word in words:
                if not word:
                    decoded_words.append("")
                    continue
                letters = word.split()
                decoded_letters = []
                for token in letters:
                    decoded_letters.append(
                        self.REVERSE_MORSE_CODE_DICT.get(token, token)
                    )
                decoded_words.append("".join(decoded_letters))
            decoded_lines.append(" ".join(decoded_words).rstrip())
        return "\n".join(decoded_lines)


class AtbashExpert:
    def encode(self, text):
        ans = ""
        N = ord("z") + ord("a")
        for s in text:
            try:
                if s.isalpha():
                    if s.isupper():
                        ans += chr(ord("Z") + ord("A") - ord(s))
                    else:
                        ans += chr(N - ord(s))
                else:
                    ans += s
            except Exception:
                ans += s
        return ans

    def decode(self, text):
        ans = ""
        N = ord("z") + ord("a")
        for s in text:
            try:
                if s.isalpha():
                    if s.isupper():
                        ans += chr(ord("Z") + ord("A") - ord(s))
                    else:
                        ans += chr(N - ord(s))
                else:
                    ans += s
            except Exception:
                ans += s
        return ans


encode_expert_dict = {
    "unchange": BaseExpert(),
    "baseline": BaseExpert(),
    "caesar": CaesarExpert(),
    "unicode": UnicodeExpert(),
    "morse": MorseExpert(),
    "atbash": AtbashExpert(),
    "utf": UTF8Expert(),
    "ascii": AsciiExpert(),
    "gbk": GBKExpert(),
    "selfdefine": SelfDefineCipher(),
}
