---
sidebar_label: client
title: hackagent.client
---

## Client Objects

```python
@define
class Client()
```

A class for keeping track of data related to the API
The following are accepted as keyword arguments and will be used to construct httpx Clients internally:
``base_url``: The base URL for the API, all requests are made to a relative path to this URL

``cookies``: A dictionary of cookies to be sent with every request

``headers``: A dictionary of headers to be sent with every request

``timeout``: The maximum amount of a time a request can take. API functions will raise
httpx.TimeoutException if this is exceeded.

``verify_ssl``: Whether or not to verify the SSL certificate of the API server. This should be True in production,
but can be set to False for testing purposes.

``follow_redirects``: Whether or not to follow redirects. Default value is False.

``httpx_args``: A dictionary of additional arguments to be passed to the ``httpx.Client`` and ``httpx.AsyncClient`` constructor.


**Attributes**:

- ``8 - Whether or not to raise an errors.UnexpectedStatus if the API returns a
  status code that was not documented in the source OpenAPI document. Can also be provided as a keyword
  argument to the constructor.

#### with\_headers

```python
def with_headers(headers: dict[str, str]) -> "Client"
```

Get a new client matching this one with additional headers

#### with\_cookies

```python
def with_cookies(cookies: dict[str, str]) -> "Client"
```

Get a new client matching this one with additional cookies

#### with\_timeout

```python
def with_timeout(timeout: httpx.Timeout) -> "Client"
```

Get a new client matching this one with a new timeout (in seconds)

#### set\_httpx\_client

```python
def set_httpx_client(client: httpx.Client) -> "Client"
```

Manually set the underlying httpx.Client

**NOTE**: This will override any other settings on the client, including cookies, headers, and timeout.

#### get\_httpx\_client

```python
def get_httpx_client() -> httpx.Client
```

Get the underlying httpx.Client, constructing a new one if not previously set

#### \_\_enter\_\_

```python
def __enter__() -> "Client"
```

Enter a context manager for self.client—you cannot enter twice (see httpx docs)

#### \_\_exit\_\_

```python
def __exit__(*args: Any, **kwargs: Any) -> None
```

Exit a context manager for internal httpx.Client (see httpx docs)

#### set\_async\_httpx\_client

```python
def set_async_httpx_client(async_client: httpx.AsyncClient) -> "Client"
```

Manually the underlying httpx.AsyncClient

**NOTE**: This will override any other settings on the client, including cookies, headers, and timeout.

#### get\_async\_httpx\_client

```python
def get_async_httpx_client() -> httpx.AsyncClient
```

Get the underlying httpx.AsyncClient, constructing a new one if not previously set

#### \_\_aenter\_\_

```python
async def __aenter__() -> "Client"
```

Enter a context manager for underlying httpx.AsyncClient—you cannot enter twice (see httpx docs)

#### \_\_aexit\_\_

```python
async def __aexit__(*args: Any, **kwargs: Any) -> None
```

Exit a context manager for underlying httpx.AsyncClient (see httpx docs)

## AuthenticatedClient Objects

```python
@define
class AuthenticatedClient()
```

A Client which has been authenticated for use on secured endpoints

The following are accepted as keyword arguments and will be used to construct httpx Clients internally:

``base_url``: The base URL for the API, all requests are made to a relative path to this URL

``cookies``: A dictionary of cookies to be sent with every request

``headers``: A dictionary of headers to be sent with every request

``timeout``: The maximum amount of a time a request can take. API functions will raise
httpx.TimeoutException if this is exceeded.

``verify_ssl``: Whether or not to verify the SSL certificate of the API server. This should be True in production,
but can be set to False for testing purposes.

``follow_redirects``: Whether or not to follow redirects. Default value is False.

``httpx_args``: A dictionary of additional arguments to be passed to the ``httpx.Client`` and ``httpx.AsyncClient`` constructor.


**Attributes**:

- ``8 - Whether or not to raise an errors.UnexpectedStatus if the API returns a
  status code that was not documented in the source OpenAPI document. Can also be provided as a keyword
  argument to the constructor.
- ``9 - The token to use for authentication
- ``0 - The prefix to use for the Authorization header
- ``1 - The name of the Authorization header

#### with\_headers

```python
def with_headers(headers: dict[str, str]) -> "AuthenticatedClient"
```

Get a new client matching this one with additional headers

#### with\_cookies

```python
def with_cookies(cookies: dict[str, str]) -> "AuthenticatedClient"
```

Get a new client matching this one with additional cookies

#### with\_timeout

```python
def with_timeout(timeout: httpx.Timeout) -> "AuthenticatedClient"
```

Get a new client matching this one with a new timeout (in seconds)

#### set\_httpx\_client

```python
def set_httpx_client(client: httpx.Client) -> "AuthenticatedClient"
```

Manually set the underlying httpx.Client

**NOTE**: This will override any other settings on the client, including cookies, headers, and timeout.

#### get\_httpx\_client

```python
def get_httpx_client() -> httpx.Client
```

Get the underlying httpx.Client, constructing a new one if not previously set

#### \_\_enter\_\_

```python
def __enter__() -> "AuthenticatedClient"
```

Enter a context manager for self.client—you cannot enter twice (see httpx docs)

#### \_\_exit\_\_

```python
def __exit__(*args: Any, **kwargs: Any) -> None
```

Exit a context manager for internal httpx.Client (see httpx docs)

#### set\_async\_httpx\_client

```python
def set_async_httpx_client(
        async_client: httpx.AsyncClient) -> "AuthenticatedClient"
```

Manually the underlying httpx.AsyncClient

**NOTE**: This will override any other settings on the client, including cookies, headers, and timeout.

#### get\_async\_httpx\_client

```python
def get_async_httpx_client() -> httpx.AsyncClient
```

Get the underlying httpx.AsyncClient, constructing a new one if not previously set

#### \_\_aenter\_\_

```python
async def __aenter__() -> "AuthenticatedClient"
```

Enter a context manager for underlying httpx.AsyncClient—you cannot enter twice (see httpx docs)

#### \_\_aexit\_\_

```python
async def __aexit__(*args: Any, **kwargs: Any) -> None
```

Exit a context manager for underlying httpx.AsyncClient (see httpx docs)

