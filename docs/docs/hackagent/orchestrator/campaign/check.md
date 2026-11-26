---
sidebar_label: check
title: hackagent.orchestrator.campaign.check
---

What is wrong with a campaign document, each problem where it is.

One check for every interface: the TUI&#x27;s builder shows its issues on the
fields they concern, `hackagent campaign validate` and `campaign run`
print them, and :func:`~hackagent.orchestrator.campaign.load_campaign`
raises them as :class:`CampaignInvalid`. Each :class:`Issue` names the
document path it is about (`attacks.0`) and says what is wrong in a
sentence, rather than a validation library&#x27;s report.

Three kinds of problem are found, in this order: an API key written into
the file instead of referenced; an attack&#x27;s parameters or roles that
resolving the campaign would reject; and anything else the campaign format
does not allow.

## Issue Objects

```python
@dataclass(frozen=True)
class Issue()
```

A problem at a document path: `attacks.0`, `Unknown attack…`.

#### where

```python
@property
def where() -> str
```

The path as written in the document: `attacks.0.parameters`.

## CampaignInvalid Objects

```python
class CampaignInvalid(ValueError)
```

A campaign document with :attr:`issues`; its message lists them, one
per line.

#### campaign\_issues

```python
def campaign_issues(
    values: Mapping[str,
                    Any]) -> tuple[Optional[CampaignSpec], tuple[Issue, ...]]
```

Check a campaign document: its spec when there is nothing to fix,
else `None` and what to fix.

#### issues\_from

```python
def issues_from(error: ValidationError) -> list[Issue]
```

A validation error&#x27;s problems, each at its path, in a sentence.

