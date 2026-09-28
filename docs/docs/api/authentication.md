---
sidebar_position: 3
sidebar_label: Authentication
---

# Authentication

Programmatic calls send the API key as a bearer token:

```http
Authorization: Bearer <api-key>
```

The key is `HACKAGENT_API_KEY` (or the `api_key` value stored by `hackagent config`). The base URL is `HACKAGENT_BASE_URL` when set, and `https://api.hackagent.dev` otherwise.

The dashboard can also sign in with Auth0. `/key` and `/organization/me` accept that session. API-key clients should call `/agent` instead. See [First request](./first-request.md).
