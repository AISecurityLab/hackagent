---
sidebar_label: defaults
title: hackagent.core.defaults
---

Default model identifiers and endpoints for the attacker, judge and helper roles.

Only plain values live here, so every package can import them. Runtime
resolution (API key, base URL, database path) belongs to
:mod:`hackagent.core.settings`.

The endpoint defaults below are computed from the environment when this
module is first imported.

#### DEFAULT\_EMBEDDER\_ENDPOINT

Where an embedder goes when nothing names a server. Resolved once, for
display and for callers that want a concrete value; the embedding path
resolves per call so a change to the environment is picked up.

