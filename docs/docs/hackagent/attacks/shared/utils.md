---
sidebar_label: utils
title: hackagent.attacks.shared.utils
---

Shared utility functions for attacks.

This module provides common helper functions used across
objectives and techniques.

#### deduplicate\_by\_content

```python
def deduplicate_by_content(items: List[str]) -> List[str]
```

Remove duplicate strings while preserving order.

**Arguments**:

- `items` - List of strings
  

**Returns**:

  Deduplicated list

#### deduplicate\_by\_hash

```python
def deduplicate_by_hash(items: List[str], hash_length: int = 8) -> List[str]
```

Remove near-duplicates using content hashing.

**Arguments**:

- `items` - List of strings
- `hash_length` - Number of hash characters to compare
  

**Returns**:

  Deduplicated list

#### encode\_base64

```python
def encode_base64(text: str) -> str
```

Encode text to base64.

#### decode\_base64

```python
def decode_base64(text: str) -> str
```

Decode base64 text.

#### simple\_obfuscate

```python
def simple_obfuscate(text: str) -> str
```

Simple text obfuscation (leetspeak-style).

**Arguments**:

- `text` - Text to obfuscate
  

**Returns**:

  Obfuscated text

#### split\_into\_chunks

```python
def split_into_chunks(text: str, chunk_size: int = 100) -> List[str]
```

Split text into chunks of specified size.

**Arguments**:

- `text` - Text to split
- `chunk_size` - Maximum chunk size
  

**Returns**:

  List of text chunks

#### normalize\_whitespace

```python
def normalize_whitespace(text: str) -> str
```

Normalize whitespace in text.

**Arguments**:

- `text` - Text to normalize
  

**Returns**:

  Text with normalized whitespace

#### truncate\_text

```python
def truncate_text(text: str,
                  max_length: int = 1000,
                  suffix: str = "...") -> str
```

Truncate text to maximum length.

**Arguments**:

- `text` - Text to truncate
- `max_length` - Maximum length
- `suffix` - Suffix to add when truncated
  

**Returns**:

  Truncated text

