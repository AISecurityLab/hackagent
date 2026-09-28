---
sidebar_position: 5
sidebar_label: Results
---

# Results

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

`POST /run/{id}/result` creates a result already tied to that run. See [Runs](./runs.md).
