---
sidebar_label: command
title: hackagent.interfaces.cli.commands.scan.command
---

The `hackagent scan &lt;url&gt;` command.

#### scan

```python
@click.command(name="scan")
@click.argument("url")
@click.option(
    "--headed",
    is_flag=True,
    help="Show the browser window instead of running it headless.",
)
@click.option(
    "--input-selector",
    default=None,
    help="CSS selector pinning the chat input box (when the built-in heuristics "
    "can't find it).",
)
@click.option(
    "--reply-selector",
    default=None,
    help=
    "CSS selector pinning the bot's reply element (skips the DOM-diff heuristic).",
)
@click.option(
    "--open-selector",
    default=None,
    help="CSS selector for the chat-launcher bubble to click first, for widgets "
    "that start collapsed (when the built-in launcher heuristics miss it).",
)
@click.option(
    "--accept-cookies/--no-accept-cookies",
    default=True,
    show_default=True,
    help="Accept/dismiss a cookie-consent banner on load (it often overlays the "
    "page and blocks the chat launcher). Use --no-accept-cookies to leave it.",
)
@click.option(
    "--llm-fallback-model",
    default=None,
    help="LiteLLM model used to read the reply from the page only when the DOM "
    "heuristics find nothing.",
)
@click.option(
    "--install-browser/--no-install-browser",
    default=True,
    show_default=True,
    help="Auto-download Chromium (~150 MB, one-time) if it's missing.",
)
@click.option(
    "--timeout",
    default=45,
    show_default=True,
    help="Page-load timeout in seconds.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    help="Print the target config (and plan, if any) as JSON and exit.",
)
@click.option(
    "--plan",
    "use_planner",
    is_flag=True,
    help="Agentic mode: an LLM inspects the target and chooses the attack "
    "strategy and parameters.",
)
@click.option(
    "--planner-model",
    default=DEFAULT_PLANNER_MODEL,
    show_default=True,
    help=
    "LiteLLM model for the --plan planner. Defaults to a local Ollama model "
    "(no API key; run `ollama pull` for it first).",
)
@click.option(
    "--attack/--no-attack",
    default=True,
    show_default=True,
    help=
    "Red-team the target. On by default; --no-attack just shows the config.",
)
@click.option(
    "--config-file",
    "config_file",
    default=None,
    type=click.Path(exists=True, dir_okay=False),
    help="YAML/JSON file supplying the attack config (a `goals:` list plus "
    "optional `attacker`, `judge`, `category_classifier`, `parameters`, "
    "`attack_type`). Commas inside goals are preserved here, unlike --goals. "
    "Explicit CLI flags (--goals, --attack-type, --attacker-model, "
    "--judge-model) override the file.",
)
@click.option(
    "--goals",
    multiple=True,
    help="Attack goals. Repeat --goals or pass a comma-separated string.",
)
@click.option(
    "--attack-type",
    default=DEFAULT_ATTACK_TYPE,
    show_default=True,
    help="Attack strategy (tap, pair, flipattack, advprefix…). Ignored when "
    "--plan picks one.",
)
@click.option(
    "--attacker-model",
    default=None,
    help="Override the attacker LLM with any LiteLLM model id "
    "(e.g. openai/gpt-4o-mini, anthropic/claude-sonnet-4-6, ollama_chat/llama3). "
    "Bypasses the auto-selected remote/local attacker. Provider key comes from "
    "the usual env var (OPENAI_API_KEY, ANTHROPIC_API_KEY, …).",
)
@click.option(
    "--judge-model",
    default=None,
    help="Override the judge/scorer LLM with any LiteLLM model id (same form as "
    "--attacker-model). Bypasses the auto-selected remote/local judge.",
)
@click.option(
    "--attack-timeout",
    default=300,
    show_default=True,
    help="Attack timeout in seconds.",
)
@click.option(
    "--no-tui",
    is_flag=True,
    help="Run the attack headless instead of opening the TUI.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Validate the wiring without executing (implies --no-tui).",
)
@click.pass_context
@handle_errors
def scan(ctx: click.Context, url: str, headed: bool, input_selector: str,
         reply_selector: str, open_selector: str, accept_cookies: bool,
         llm_fallback_model: str, install_browser: bool, timeout: int,
         as_json: bool, use_planner: bool, planner_model: str, attack: bool,
         config_file: Optional[str], goals: Tuple[str, ...], attack_type: str,
         attacker_model: str, judge_model: str, attack_timeout: int,
         no_tui: bool, dry_run: bool) -> None
```

🌐 Red-team a website&#x27;s chatbot via a real browser.

Points the `web` provider at URL: it drives the live page in a browser,
typing each prompt into the chat widget and reading the reply from the page —
so it works on any chat UI regardless of transport (WebSocket/SSE/HTTP). Add
`--plan` to let an LLM choose the strategy; `--no-attack` to just print the
target config.



**Examples**:

  hackagent scan https://www.example.com
  hackagent scan https://www.example.com --plan
  hackagent scan https://www.example.com --headed --input-selector &#x27;textarea&#x27;
  hackagent scan https://www.example.com --config-file goals.yaml --no-tui
  hackagent scan https://www.example.com --no-attack --json

