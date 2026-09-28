---
sidebar_position: 6
sidebar_label: Errors
---

# Errors

A failed call returns its HTTP status and response body. List calls succeed with `200`. Create calls succeed with `201`.

There is no separate error envelope in these docs yet. Clients should treat any other status as a failure and read the body.

The Python SDK raises `UnexpectedStatus` (status code and raw body) only when `raise_on_unexpected_status` is true. Otherwise that client returns no parsed body. `ApiError` is the SDK exception for a failed API call.
