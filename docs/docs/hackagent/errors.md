---
sidebar_label: errors
title: hackagent.errors
---

Contains shared errors types that can be raised from API functions

## UnexpectedStatus Objects

```python
class UnexpectedStatus(Exception)
```

Raised by api functions when the response status an undocumented status and Client.raise_on_unexpected_status is True

## HackAgentError Objects

```python
class HackAgentError(Exception)
```

Base exception class for HackAgent errors

## ApiError Objects

```python
class ApiError(HackAgentError)
```

Raised when an API call fails

