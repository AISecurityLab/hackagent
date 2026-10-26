---
sidebar_label: credentials
title: hackagent.core.credentials
---

Resolve the single `api_key` input and serialize only safe references.

## CredentialError Objects

```python
class CredentialError(ValueError)
```

A selected credential is empty, missing or invalid.

#### resolve\_api\_key

```python
def resolve_api_key(api_key: Optional[str] = None,
                    *,
                    use_default: bool = False,
                    required: bool = False,
                    purpose: str = "API key",
                    env: Optional[Mapping[str, str]] = None) -> Optional[str]
```

Resolve a value or explicit `${VARIABLE}`; never guess variable names.

Only platform connections opt into the HACKAGENT_API_KEY default. A
selected reference or explicit empty value never falls back elsewhere.

#### credential\_reference

```python
def credential_reference(api_key: Optional[str]) -> Optional[str]
```

Return only the original reference; a runtime value is never exported.

#### validate\_file\_credentials

```python
def validate_file_credentials(value: Any) -> None
```

Validate file references without resolving sources a caller may override.

#### prepare\_credentials

```python
def prepare_credentials(value: Any,
                        *,
                        from_file: bool = False,
                        env: Optional[Mapping[str, str]] = None) -> Any
```

Copy input data, rejecting file secrets before validation can echo them.

#### is\_gateway\_endpoint

```python
def is_gateway_endpoint(endpoint: Optional[str], base_url: str) -> bool
```

Match the exact configured gateway origin and path, excluding lookalikes.
