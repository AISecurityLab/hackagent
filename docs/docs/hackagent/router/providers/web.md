---
sidebar_label: web
title: hackagent.router.providers.web
---

The ``web`` provider — red-teams a website&#x27;s chatbot by driving the live page.

This makes **the live website itself the target**: it keeps a real browser page
open and, for every prompt the attack loop sends, types it into the chat widget,
submits, and reads the assistant&#x27;s reply back out of the rendered DOM. There is
no endpoint reverse-engineering, request template, or response path — it
interacts at the UI level the way a person does, so it works on any web chat
**regardless of transport** (WebSocket, SSE, multipart, obfuscated URLs) and
keeps auth/session/CSRF state naturally because the browser holds it. This is
the general approach: point it at a URL and it just works, where HTTP
capture-and-replay does not.

Reply reading is **DOM-heuristics-first**: after sending, it diffs the page&#x27;s
message elements to find the new assistant turn and waits for streamed text to
settle. An optional ``reply_selector`` pins the reply element, ``input_selector``
pins the chat box, and ``llm_fallback_model`` extracts the reply via an LLM only
when the heuristics come up empty.

Trade-off: a real browser round-trip per prompt is slower than an HTTP call, and
calls are serialized (one shared page), so concurrent attack streams run
sequentially. Like the other gap-filler providers it registers a per-instance
:class:`litellm.CustomLLM` so requests flow through ``litellm.completion`` and
the tracking logger.

Playwright ships with hackagent; the Chromium binary it drives is fetched
automatically on first use.

## WebAgentConfigurationError Objects

```python
class WebAgentConfigurationError(AdapterConfigurationError)
```

Web-agent configuration issues (e.g. missing url / browser unavailable).

## WebAgentInteractionError Objects

```python
class WebAgentInteractionError(AdapterInteractionError)
```

Errors driving the live page (input not found, no reply, …).

## WebAgent Objects

```python
class WebAgent(Agent)
```

Adapter that red-teams a website&#x27;s chatbot by driving the live page.

Required config:
    - ``url`` (or ``endpoint``): the page hosting the chatbot.

Optional config:
    - ``name``: label / model string (defaults to the URL host).
    - ``headless`` (default True): set False to watch the interaction.
    - ``timeout`` (page-load seconds, default 30).
    - ``wait_after_send`` (seconds to wait for a reply, default 20).
    - ``settle_ms`` (widget init wait after load, default 1500).
    - ``input_selector``: CSS selector pinning the chat input box (skips the
      built-in input-location heuristics).
    - ``reply_selector``: CSS selector pinning the reply element (skips the
      DOM-diff heuristic).
    - ``launcher_selector``: CSS selector for the chat-launcher bubble to
      click open first, for widgets that start collapsed (skips the
      built-in launcher heuristics).
    - ``dismiss_consent`` (default True): accept/dismiss a cookie-consent
      banner on load so it can&#x27;t intercept clicks on the chat launcher.
    - ``llm_fallback_model``: LiteLLM model used to read the reply only when
      the heuristics find nothing.

#### probe\_ready

```python
def probe_ready() -> Optional[str]
```

Non-invasive reachability check for preflight.

Starts the browser session and confirms the chat input is locatable
WITHOUT sending a message — so the availability probe never types a
junk &quot;healthcheck&quot; into the live chatbot (which would contaminate the
real conversation and the recorded transcript). Returns None when the
widget is reachable, or an error string otherwise.

#### handle\_request

```python
def handle_request(request_data: Dict[str, Any]) -> Dict[str, Any]
```

Send a single turn to the live page via ``litellm.completion``.

