# Red-teaming a website chatbot (the `web` provider)

The `web` provider makes a **live website the target**. For every attack prompt
it drives a real browser (Playwright): it loads the page, types the prompt into
the chat widget, submits, and reads the reply from the rendered DOM. There's no
endpoint reverse-engineering and no HTTP replay, so it works on **any** chat UI
regardless of transport — WebSocket, SSE, plain HTTP, obfuscated endpoints — and
auth/session/CSRF state "just works" because the browser holds it.

## ⚠️ Authorization

A chatbot on someone else's website is a **third-party production system**. Only
test a target you are authorized to test — your own system, a contracted
engagement, or written permission. Edit the `endpoint` and `url` in
`tap-site-chatbot.yaml` to the site you are testing before running it.

## Install

```bash
pip install 'hackagent[browser]'   # Playwright; Chromium is fetched on first run
```

The planner and the example attacker/judge default to a **local Ollama** model —
no API key. Pull it once:

```bash
ollama pull Librellama/gemma4:e2b-Uncensored   # uncensored → won't refuse to plan red-team prompts
```

## Run it

`tap-site-chatbot.yaml` is a campaign file: copy it, set the site in it, check
it, run it. `hackagent examples web` prints where the bundled copy is. The
attacker and judge run on local Ollama, so no API key is needed.

```bash
hackagent campaign validate tap-site-chatbot.yaml   # resolves everything, attacks nothing
hackagent campaign run tap-site-chatbot.yaml
```

When the input/reply heuristics miss a site's widget, pin them with
`input_selector` and `reply_selector` under `target.options` (see below).

Plan a strategy (read-only — does not touch the target):

```bash
python plan.py https://www.example.com
```

Wiring the target by hand:

```yaml
target:
  name: site-chatbot
  connection:
    provider: web
    type: WEB
    endpoint: https://host/chat
  options:
    url: https://host/chat
    headless: true                       # false to watch the browser
    # input_selector: textarea           # pin the chat box if needed
    # reply_selector: .bot:last-child    # pin the reply element if needed
    # llm_fallback_model: anthropic/claude-haiku-4-5   # read the reply via an LLM
```

### Config reference (`web`)

| Key | Default | Meaning |
|-----|---------|---------|
| `url` (or `connection.endpoint`) | — (required) | The page hosting the chatbot |
| `name` | URL host | Label / model string |
| `headless` | `true` | Set false to watch the browser |
| `timeout` | `30` | Page-load timeout (seconds) |
| `input_selector` | auto | CSS selector for the chat input (when heuristics miss it) |
| `reply_selector` | auto | CSS selector for the reply element (skips DOM-diff) |
| `llm_fallback_model` | none | LiteLLM model to read the reply only when heuristics find nothing |
| `install_browser` | `true` | Auto-download Chromium if missing |

## Trade-off

A real browser round-trip per prompt is **slower** than an HTTP call, and calls
are serialized (one shared page), so concurrent attack streams run sequentially.
The upside is generality: point it at a URL and it works.
