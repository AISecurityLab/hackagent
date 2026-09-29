---
sidebar_label: HTTP API
---

# HTTP API

The HackAgent HTTP API is the remote service at `https://api.hackagent.dev`. Use it for remote automation, including clients that are not Python.

Python classes and the generated module pages are the [SDK](../sdk/python-quickstart.md). The local `hackagent web` dashboard is the [CLI web command](../cli/web.md). This page does not document those.

The default base URL is `https://api.hackagent.dev`. Override it with `HACKAGENT_BASE_URL`.

## First request

`GET /agent` is the call that accepts an API key. A 200 response is a paginated list of agents for that key.

```bash
curl -sS \
  -H "Authorization: Bearer $HACKAGENT_API_KEY" \
  https://api.hackagent.dev/agent
```

Set the key as described in [Authentication](#authentication). To use another host, replace the origin with `HACKAGENT_BASE_URL`.

`/key` and `/organization/me` are Auth0-only on the deployed API. Do not use them as the API-key check.

## Authentication

Programmatic calls send the API key as a bearer token:

```http
Authorization: Bearer <api-key>
```

The key is `HACKAGENT_API_KEY` (or the `api_key` value stored by `hackagent config`). The base URL is `HACKAGENT_BASE_URL` when set, and `https://api.hackagent.dev` otherwise.

The dashboard can also sign in with Auth0. `/key` and `/organization/me` accept that session. API-key clients should call `/agent` instead.

## Runs

Runs are the remote record of an evaluation. The service exposes:

| Method | Path | Role |
| --- | --- | --- |
| `GET` | `/run` | List runs |
| `POST` | `/run` | Create a run (`201` and a run object) |
| `GET` | `/run/{id}` | Retrieve one run |
| `PUT` | `/run/{id}` | Replace one run |
| `PATCH` | `/run/{id}` | Update one run |
| `DELETE` | `/run/{id}` | Delete one run |
| `POST` | `/run/{id}/result` | Attach a result to a run |
| `POST` | `/run/run_tests` | Start a server-side test run (`200`) |

Listing and retrieving are the primary operations on `/run`. Server-side runs are also created through custom actions such as `POST /run/run_tests`. List responses are paginated.

## Results

Results are the per-attempt rows for a run. The service exposes:

| Method | Path | Role |
| --- | --- | --- |
| `GET` | `/result` | List results. Filter with `run` or `evaluation_status` |
| `POST` | `/result` | Create a result (`201` and a result object) |
| `GET` | `/result/{id}` | Retrieve one result |
| `PUT` | `/result/{id}` | Replace one result |
| `PATCH` | `/result/{id}` | Update one result |
| `DELETE` | `/result/{id}` | Delete one result |
| `POST` | `/result/{id}/trace` | Attach a trace to a result |

`POST /run/{id}/result` creates a result already tied to that run.

## Errors

A failed call returns its HTTP status and response body. List calls succeed with `200`. Create calls succeed with `201`.

There is no separate error envelope yet. Clients should treat any other status as a failure and read the body.

The Python SDK raises `UnexpectedStatus` (status code and raw body) only when `raise_on_unexpected_status` is true. Otherwise that client returns no parsed body. `ApiError` is the SDK exception for a failed API call.
