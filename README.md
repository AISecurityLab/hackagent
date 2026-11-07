<div align="center">

<img src="https://docs.hackagent.dev/img/banner.svg" alt="HackAgent" width="800">

**The open-source red-team toolkit for AI models and agents**

[Docs](https://docs.hackagent.dev/) · [App](https://app.hackagent.dev/) · [API](https://api.hackagent.dev/schema/redoc)

[![PyPI](https://img.shields.io/pypi/v/hackagent)](https://pypi.org/project/hackagent/)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-green)
![CI](https://img.shields.io/github/actions/workflow/status/AISecurityLab/hackagent/ci.yml)
![Coverage](https://img.shields.io/codecov/c/github/AISecurityLab/hackagent)

</div>

HackAgent attacks your AI model or agent with research-backed techniques —
jailbreaks, prompt injection, tool misuse — and has judge models score every
reply. You get a measured success rate per attack, so you can see how exposed a
target is and whether a fix helped.

## See it run

**Terminal UI.** Start from an example, change what you need, run it.

<img src="https://raw.githubusercontent.com/AISecurityLab/hackagent/main/docs/static/gifs/hackagent-tui.gif" alt="Building and running a campaign in the HackAgent terminal UI" width="100%">

**Command line.** The same campaign is one YAML file you can edit, check and run, in a shell or in CI.

<img src="https://raw.githubusercontent.com/AISecurityLab/hackagent/main/docs/static/gifs/hackagent-cli.gif" alt="Copying, editing, validating and running a campaign from the command line" width="100%">

**Dashboard.** Browse runs, results and traces with `hackagent web`, or on [app.hackagent.dev](https://app.hackagent.dev/).

Local campaign-list summaries, full campaign dashboard detail, goal coverage,
and costs are materialized in versioned
`dashboard_snapshots` rows in the same SQLite database. A background web-server
worker checks active campaigns every 30 seconds and atomically publishes each
campaign's counts and costs from a consistent read snapshot. Initial backfill
shows a preparing state; subsequent requests load persisted data with its
generation time. Once a campaign and all its attack runs are completed, failed,
or cancelled, the worker captures a final snapshot and excludes it from
subsequent refreshes, revision scans, and aggregation. Missing snapshots and old
snapshot versions are backfilled; reopening a campaign makes it eligible again.
If all snapshots are final, the worker skips copying the source database.
Unchanged active campaigns are not re-aggregated. Refresh failures
retain previous data and report the error. This is best-effort freshness:
large backfills and database contention may take longer than 30 seconds.
The worker runs while the local web server is open, not inside attack execution.
Conversations, raw evidence, and run-scoped investigation still read their original
records. HTML exports explicitly request fresh detail, goals, and costs and retain their consistency
checks. Deleting a campaign also deletes its stored dashboard snapshot.
Background cache writes use a separate connection so a cache write waiting for
a database lock does not hold the HTTP store's thread mutex.

Judge agreement compares votes on the same recorded response, before the judge
audit. Version-11 snapshots declare `unit=attempt`; each response counts once.
The agreement table offers Micro · Attempts (default) and Macro · Goals frequencies.
Micro pools all responses; macro gives each recorded goal one unit, divided equally among its
attempts in that column. Campaign weights pool matching goal indices across
attacks; each attack uses its own recorded goals and attempts. Goals without
attempts are not included. Recorded outcomes and same-response judge identities
are unchanged: this is not ASR@goal, nor a goal-level judge verdict.
`goal_weighted` stores the goal denominator and joint outcome/pattern weights.
Missing goal identities make weights unavailable, never inferred from totals.
Exact pattern strings preserve judge identity in the sorted `judges` array order:
`1` jailbreak, `0` mitigation, `?` abstaining/missing/invalid. Histograms are stored
both campaign-wide and per attack run. Unknown votes never become negative.
Per-judge jailbreak rates use valid votes; pairwise rates use shared valid attempts.
Explicit abstentions, missing fields, and invalid votes are reported separately;
score averages are excluded. These summaries are persisted with dashboard detail.
Agreement does not measure accuracy; historical panels expose only judge fields
that were actually recorded.
Fleiss' kappa reuses the evaluation metrics implementation on complete-panel
binary votes. It is reported as undefined for fewer than two judges, no complete
attempts, or a single vote class (chance agreement equals one), rather than
displaying a misleading perfect score. Majority-positive rate, per-judge safe
vote rates (strictness), and their maximum-minus-minimum gap reuse the same
evaluation helpers. Aggregated panel score means cannot be recovered from binary
fields and are not fabricated.
Vote-count histograms retain both the number of valid votes and the number of
jailbreak votes, so 1-of-3 and 2-of-3 split attempts stay distinct, and partial
panels are never pooled with complete panels.
Outcome/vote histograms retain the recorded final result bucket for every
attempt, including unanimous and insufficient votes, both campaign-wide and
per attack run. The dashboard displays exact observed judge patterns using
coverage-style squares in a single frequency matrix. Recorded final outcomes are
parent rows; indented judge patterns are children, kept expanded. The first
column pools all attempts, followed by attack columns. Parent and child shares
use all attempts in their column, so children sum to the parent.
`outcome_patterns` persists the joint outcome/identity counts, campaign-wide and
per attack, without inferring outcomes from majority votes. The same pattern may
appear under multiple final outcomes. Missing/error
verdicts remain explicit, never counted as mitigation. Older snapshots remain
visible while this additional breakdown is materialized in the background.
The campaign list supports `progressive=1`: ready summaries are returned
immediately, with unprepared campaign identities separately and stable page
positions. Missing summaries never become fabricated zero counts.
Compatible saved snapshots remain available during summary-version upgrades,
with an explicit upgrading marker; only campaigns without a usable snapshot
show preparation. Local dead-worker leases are recovered using host/PID
ownership. The CLI stops the previous server before starting the new worker,
and handles SIGTERM through its cleanup path.

In local campaign coverage, each attack's evaluated goal outcomes appear while
other goals are still running. Pending evaluations and errors remain unresolved.
The pooled campaign verdict stays unresolved until the campaign finishes unless
an attack has already jailbroken that goal.

Time to first jailbreak measures per-goal execution through the earliest
successful target response. It includes rewriting and intervening judging, but
excludes local concurrency-slot waits, final judging, and shared run preparation.
Server-side queueing remains included. Legacy queue-inclusive clocks are not
substituted when execution timing is unavailable.

<img src="https://raw.githubusercontent.com/AISecurityLab/hackagent/main/docs/static/gifs/hackagent-dashboard.gif" alt="Browsing campaign results in the HackAgent dashboard" width="100%">

## Quick start

```bash
pip install 'hackagent[tui]'
hackagent                # opens the terminal UI
```

Or run an example end to end, fully local, with [Ollama](https://ollama.com):

```bash
ollama pull gemma3:4b
hackagent examples copy h4rm3l-demo
hackagent campaign run h4rm3l-demo.yaml
```

No API key needed: results go to a local database unless a campaign says
otherwise.

## Learn more

- [Installation](https://docs.hackagent.dev/getting-started/installation) — extras, and standalone binaries that need no Python
- [Your first campaign](https://docs.hackagent.dev/getting-started/first-campaign) — write, check and run one
- [Concepts](https://docs.hackagent.dev/concepts) — attacks, judges and how a run works
- [Attacks](https://docs.hackagent.dev/reference/attacks) and the [campaign file reference](https://docs.hackagent.dev/reference/campaign)
- [Dashboard](https://docs.hackagent.dev/getting-started/dashboard) — `hackagent web`, locally or against your account

Questions? Join the [discussions](https://github.com/AISecurityLab/hackagent/discussions) or email ais@ai4i.it.

## Responsible use

HackAgent is for authorized security testing only. Test systems you own or
have written permission to test, and report what you find through coordinated
disclosure. Read the [responsible disclosure guidelines](https://docs.hackagent.dev/security/responsible-disclosure)
and our [security policy](SECURITY.md).

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

Licensed under Apache-2.0. See [LICENSE](LICENSE). HackAgent is intended for
security research and AI safety improvement; the authors are not responsible
for misuse.
