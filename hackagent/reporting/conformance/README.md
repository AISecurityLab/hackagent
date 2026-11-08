# Campaign run report conformance

`sample.json` is one canonical data set; `cases.json` lists requests against
it and the exact response each must get, with bodies in `expected/`. The SDK's
local server (`hackagent web`) and the platform API both load the sample and
replay every case. Read them with `hackagent.reporting.conformance`
(`sample()`, `cases()`, `normalized()`).

## The sample

Plain JSON, one list per table. Every id is a fixed UUID and every timestamp a
fixed ISO 8601 string in UTC; store them as they are.

| list | fields |
|---|---|
| `agents` | `id`, `name`, `created_at` |
| `campaigns` (saved plans) | `id`, `name`, `agent`, `created_at` |
| `attacks` | `id`, `type`, `agent`, `configuration`, `created_at` |
| `campaign_runs` (parent runs) | `id`, `name`, `campaign` (or null), `agent`, `status`, `executor` (`local` or `cli`), `configuration` (the campaign spec), `audit` (or null), `notes` (or null), `revision`, `created_at`, `updated_at`, `finished_at` (or null) |
| `attack_runs` (child runs) | `id`, `campaign_run`, `attack`, `agent`, `status`, `configuration` (`run_config`), `notes` (or null), `created_at`, `updated_at` |
| `results` | `id`, `run` (attack run), `goal`, `goal_index`, `request_payload`, `agent_specific_data`, `evaluation_status`, `evaluation_notes` (or null), `latency_ms` (or null), `created_at`, `updated_at` |
| `traces` | `id`, `result`, `sequence`, `step_type`, `content`, `timestamp` |

`null` notes mean "no notes"; a store that keeps an empty string instead
stores `''`. As the runner writes it, a result's `agent_specific_data`
repeats its `latency_ms`. `step_type` includes `interaction`, the step the
runner records for every target exchange.

## Loading it

1. Insert agents, campaigns, attacks, campaign runs and attack runs with the
   sample's ids and timestamps.
2. Write each result and its traces through the same code path a real run
   uses, so the per-goal tallies (`goal_outcome`, `goal_usage`) are kept by
   the production write path: the result, then its traces in `sequence`
   order, then its evaluation (`evaluation_status`, `evaluation_notes`,
   `agent_specific_data`, `latency_ms`).
3. Then overwrite every timestamp the writes set (`created_at`/`timestamp`,
   `updated_at` of results; `updated_at` of runs) with the sample's, and
   recompute the tallies' timestamps if they were taken from the clock.
4. Finally set each campaign run's `revision` to the sample's value: the
   writes bump it, and how many times is each server's own business. The
   ETags in the cases are computed from these values.

## The cases

Each case has `name`, `method`, `path` (below the API root: `/run/summary`;
the local server serves `/api/proxy/run/summary`), `query` (`[key, value]`
pairs in request order), `headers`, `body` (JSON or null), `status`, `etag`
(the response's `ETag`, or null when it must have none) and `expected` (a file
in `expected/`, or null for a response without a body). Compare a body after
`normalized()`, which turns a page's `next`/`previous` links into booleans:
their form is each server's own.

A case with `mutates: true` deletes data: run it against a freshly loaded
sample. All others leave the store as it was.

Not in the cases, because they need a write: after any write that changes a
campaign run's report (a result, a trace, an attack run's or the campaign
run's status), the next `GET` with the old ETag must answer `200` with a new
ETag. Each server tests that itself.
