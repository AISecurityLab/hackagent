---
sidebar_label: taxonomy
title: hackagent.datasets.taxonomy
---

The risk taxonomy goals are labelled with, read from `taxonomy.yaml`.

Categories are letters (`E`), subcategories a letter and a number (`E2`).
A goal&#x27;s labels pair them in display form, `E. Cybersecurity Threats` and
`E2. Exploit Development`; the category always follows from the
subcategory. A goal whose category is known but not its subcategory gets
the category&#x27;s `0` subcategory (`E0. Unspecified Subcategory`), which no
taxonomy entry uses; one known by neither is `Z`/`Z0`, unclassified.

#### categories

```python
def categories() -> dict[str, str]
```

Category code to label, in taxonomy order.

#### subcategories

```python
def subcategories(category: str | None = None) -> dict[str, str]
```

Subcategory code to label, optionally only those of `category`.

#### labels

```python
def labels(subcategory: str) -> dict[str, str]
```

A goal&#x27;s labels for a subcategory code.

#### unspecified

```python
def unspecified(category: str) -> dict[str, str]
```

A goal&#x27;s labels when only its category is known: `C` and `C0`.

#### describe

```python
def describe() -> str
```

The taxonomy as a model reads it: one code and label per line.

#### resolve\_category

```python
def resolve_category(value: Any) -> str
```

A category&#x27;s code from its code, label, or display form.

#### resolve\_subcategory

```python
def resolve_subcategory(value: Any) -> str
```

A subcategory&#x27;s code from its code, label, or display form.

#### IntentCategory

Members by name (`CYBERSECURITY_THREATS`) and by code (`E`).

