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
engagement, or written permission. `hack.py` refuses to run unless you set
`HACKAGENT_AUTHORIZED=1`.

## Install

```bash
pip install hackagent      # Playwright is included; Chromium auto-fetched on first run
```

The planner and the example attacker/judge default to a **local Ollama** model —
no API key. Pull it once:

```bash
ollama pull huihui_ai/gemma3-abliterated:12b   # abliterated → won't refuse to plan red-team prompts
```

## One command (CLI)

```bash
hackagent scan https://www.example.com                 # drive the page + attack (TUI)
hackagent scan https://www.example.com --plan          # + an LLM picks the strategy
hackagent scan https://www.example.com --no-attack     # just show the target config
hackagent scan https://www.example.com --headed --no-tui   # watch it, run headless
```

When the input/reply heuristics miss a site's widget, pin them:

```bash
hackagent scan https://www.example.com \
  --input-selector 'textarea' \
  --reply-selector '.bot-message:last-child'
```

## Programmatic

Plan a strategy (read-only — does not touch the target):

```bash
python plan.py https://www.example.com
```

Run an authorized attack (attacker/judge run on local Ollama — no API key):

```bash
export TARGET_URL="https://www.your-authorized-site.com"
export HACKAGENT_AUTHORIZED=1
python hack.py
```

Wiring it by hand:

```python
from hackagent import HackAgent

agent = HackAgent(
    name="site-chatbot",
    endpoint="https://host/chat",
    agent_type="web",
    adapter_operational_config={
        "url": "https://host/chat",
        "headless": True,                       # False to watch the browser
        # "input_selector": "textarea",          # pin the chat box if needed
        # "reply_selector": ".bot:last-child",   # pin the reply element if needed
        # "llm_fallback_model": "anthropic/claude-haiku-4-5",  # read reply via LLM if heuristics miss
    },
)
```

### Config reference (`web`)

| Key | Default | Meaning |
|-----|---------|---------|
| `url` (or `endpoint`) | — (required) | The page hosting the chatbot |
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
