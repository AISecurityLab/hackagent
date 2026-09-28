---
sidebar_position: 2
sidebar_label: First request
---

# First request

`GET /agent` is the call that accepts an API key. A 200 response is a paginated list of agents for that key.

```bash
curl -sS \
  -H "Authorization: Bearer $HACKAGENT_API_KEY" \
  https://api.hackagent.dev/agent
```

Set the key as described in [Authentication](./authentication.md). To use another host, replace the origin with `HACKAGENT_BASE_URL`.

`/key` and `/organization/me` are Auth0-only on the deployed API. Do not use them as the API-key check.
