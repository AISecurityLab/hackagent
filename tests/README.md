# Testing Hackagent

The default suite runs offline component tests, deterministic integrations, and
end-to-end tests. Real model/backend checks require an explicit opt-in. A test's
`integration` marker describes its scope; it does not imply a service dependency.
Service markers (`google_adk`, `ollama`, `openai_sdk`, `litellm`) are gated centrally
in `tests/conftest.py`. `live` tests require `--run-live`, registered at the root so
it is available with explicit test paths too.

## Required pull request checks

```sh
uv run pytest tests/unit
uv run pytest tests/integration/offline tests/integration/tui --fail-on-skip
uv run pytest tests/e2e --fail-on-skip
```

The deterministic lanes run on every PR. `--fail-on-skip` makes a missing
prerequisite a failure rather than a green job with skipped cases. Ordinary pytest
already fails when no cases are collected. JUnit artifacts record individual
outcomes. A deferred TUI snapshot remains an expected failure in the unit suite.

The local completion fixture in `tests/support/campaigns.py` replaces only the
external provider. The real model factory, HTTP clients, retries, campaign runner,
judges, trackers, SQLite and output serializers execute. It records requests and
rejects unexpected paths/models. CLI tests launch fresh processes from a temporary
working directory with isolated configuration, credentials and storage. They
assert exact exchanges, final state, trace persistence and JSON/JSONL agreement.

Do not mock the runner or Store to write an integration test. Component tests may
continue to use small fakes. For successful transport tests require no response
error and a nonempty reply; intentional failures belong in separate cases. Do not
catch broad exceptions around assertions or fetch Hub datasets from unit tests.

Markup tests invoke production formatters and mount ResultsTab over a real SQLite
store. Verify literal content, not just absence of rendering exceptions.

## Real service checks

```sh
uv run pytest tests/integration/models --run-google-adk --fail-on-skip
uv run pytest tests/live --run-live
```

The ADK fixture can launch an ADK agent over a local Ollama instance. Provision
its model before invoking a required lane. Hosted auth is a live backend smoke
check requiring `HACKAGENT_API_KEY` and `HACKAGENT_API_BASE_URL`; it is not a
campaign e2e test. Do not point tests at production data or accounts.

`--run-integration` remains a compatibility alias enabling service integration
checks. Use a specific provider flag for focused local runs. The existing live
suite remains optional; this change does not create new scheduled jobs.

## Next implementation slices

1. Extend the HTTP harness to stateful ADK and remote API protocol fixtures,
   validating the latter against the API schema and an isolated API deployment.
2. Add adaptive/multi-turn exchanges, preflight failure, guardrail blocking,
   concurrency and cancellation with exact request and terminal-state assertions.
3. Cover claims, heartbeat, credit exhaustion and write/flush failures through real
   remote transport. Keep remote schema and fixture compatibility visible in CI.
4. Maintain the compiled-dashboard Playwright smoke with expected record contents,
   navigation and browser/server diagnostics. Its seed contract has a regression
   test; the browser itself is not provisioned by these new deterministic lanes.
5. Add clean wheel/extras installation and release-binary execution outside the
   checkout, followed by registry-driven attack/judge contracts and focused live
   compatibility checks.
6. Establish branch/patch baselines including the TUI and separating generated
   clients. Configure subprocess coverage before using CLI coverage percentages
   as a release gate; ordinary pytest coverage does not measure child CLI code.

Favor one contract scenario per registry entry plus representative cross-component
journeys over an attack × provider × judge Cartesian product. Keep model quality
benchmarks separate from deterministic application regression checks.
