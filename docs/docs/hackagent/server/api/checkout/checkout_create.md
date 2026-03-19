---
sidebar_label: checkout_create
title: hackagent.server.api.checkout.checkout_create
---

#### sync\_detailed

```python
def sync_detailed(
    *,
    client: AuthenticatedClient,
    body: CheckoutSessionRequestRequest
    | CheckoutSessionRequestRequest
    | CheckoutSessionRequestRequest
    | Unset = UNSET
) -> Response[CheckoutSessionResponse | GenericErrorResponse]
```

Create Stripe Checkout Session

Initiates a Stripe Checkout session for purchasing API credits.
The user must be authenticated.
The number of credits to purchase must be provided in the request body.

**Arguments**:

  body (CheckoutSessionRequestRequest):
  body (CheckoutSessionRequestRequest):
  body (CheckoutSessionRequestRequest):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[CheckoutSessionResponse | GenericErrorResponse]

#### sync

```python
def sync(
    *,
    client: AuthenticatedClient,
    body: CheckoutSessionRequestRequest
    | CheckoutSessionRequestRequest
    | CheckoutSessionRequestRequest
    | Unset = UNSET
) -> CheckoutSessionResponse | GenericErrorResponse | None
```

Create Stripe Checkout Session

Initiates a Stripe Checkout session for purchasing API credits.
The user must be authenticated.
The number of credits to purchase must be provided in the request body.

**Arguments**:

  body (CheckoutSessionRequestRequest):
  body (CheckoutSessionRequestRequest):
  body (CheckoutSessionRequestRequest):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  CheckoutSessionResponse | GenericErrorResponse

#### asyncio\_detailed

```python
async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    body: CheckoutSessionRequestRequest
    | CheckoutSessionRequestRequest
    | CheckoutSessionRequestRequest
    | Unset = UNSET
) -> Response[CheckoutSessionResponse | GenericErrorResponse]
```

Create Stripe Checkout Session

Initiates a Stripe Checkout session for purchasing API credits.
The user must be authenticated.
The number of credits to purchase must be provided in the request body.

**Arguments**:

  body (CheckoutSessionRequestRequest):
  body (CheckoutSessionRequestRequest):
  body (CheckoutSessionRequestRequest):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  Response[CheckoutSessionResponse | GenericErrorResponse]

#### asyncio

```python
async def asyncio(
    *,
    client: AuthenticatedClient,
    body: CheckoutSessionRequestRequest
    | CheckoutSessionRequestRequest
    | CheckoutSessionRequestRequest
    | Unset = UNSET
) -> CheckoutSessionResponse | GenericErrorResponse | None
```

Create Stripe Checkout Session

Initiates a Stripe Checkout session for purchasing API credits.
The user must be authenticated.
The number of credits to purchase must be provided in the request body.

**Arguments**:

  body (CheckoutSessionRequestRequest):
  body (CheckoutSessionRequestRequest):
  body (CheckoutSessionRequestRequest):
  

**Raises**:

- `errors.UnexpectedStatus` - If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
- `httpx.TimeoutException` - If the request takes longer than Client.timeout.
  

**Returns**:

  CheckoutSessionResponse | GenericErrorResponse

