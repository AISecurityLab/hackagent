---
sidebar_position: 4
sidebar_label: Runs
---

# Runs

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

Listing and retrieving are the primary operations on `/run`. Server-side runs are also created through custom actions such as `POST /run/run_tests`. `POST /run` returns `201`.

List responses are paginated. Send the bearer token from [Authentication](./authentication.md). Result rows are documented in [Results](./results.md).
