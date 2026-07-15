# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
The ``web`` provider — red-teams a website's chatbot by driving the live page.

This makes **the live website itself the target**: it keeps a real browser page
open and, for every prompt the attack loop sends, types it into the chat widget,
submits, and reads the assistant's reply back out of the rendered DOM. There is
no endpoint reverse-engineering, request template, or response path — it
interacts at the UI level the way a person does, so it works on any web chat
**regardless of transport** (WebSocket, SSE, multipart, obfuscated URLs) and
keeps auth/session/CSRF state naturally because the browser holds it. This is
the general approach: point it at a URL and it just works, where HTTP
capture-and-replay does not.

Reply reading is **DOM-heuristics-first**: after sending, it diffs the page's
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
"""

import atexit
import re
import threading
from typing import Any, Dict, List, Optional

from hackagent.logger import get_logger
from hackagent.router import envelope as _envelope
from hackagent.router.agent import (
    Agent,
    AdapterConfigurationError,
    AdapterInteractionError,
)

logger = get_logger(__name__)

_litellm_module = None


def _get_litellm():
    """Lazily import litellm. Returns ``(module, is_available)``."""
    global _litellm_module
    if _litellm_module is not None:
        return _litellm_module, True
    try:
        import litellm

        _litellm_module = litellm
        return litellm, True
    except ImportError:
        return None, False


class WebAgentConfigurationError(AdapterConfigurationError):
    """Web-agent configuration issues (e.g. missing url / browser unavailable)."""


class WebAgentInteractionError(AdapterInteractionError):
    """Errors driving the live page (input not found, no reply, …)."""


_WEB_PROVIDER_PREFIX = "hackagent_web"

# CSS selectors for chat *message* elements, tried across all frames. Broad on
# purpose — the reply is found by diffing message text before/after sending, so
# false positives in the selector set are filtered out by the diff.
_MESSAGE_SELECTORS = (
    "[data-message-author-role]",
    "[class*=message i]",
    "[class*=msg i]",
    "[class*=bubble i]",
    "[class*=response i]",  # e.g. chat-item-response-text-wrapper
    "[class*=chat i] [class*=text i]",
    "[role=listitem]",
)

# Collect message-bubble texts in ONE round-trip per frame, EXCLUDING bubbles
# that are the user's own turn — so the echoed prompt (and any junk a reasoning
# attacker types in) never contaminates the captured reply. A bubble is "user"
# when an author marker on it or an ancestor says so; an assistant marker wins
# (kept), and bubbles with no marker are kept (current behaviour).
_MESSAGE_EXTRACT_JS = r"""
(selectors) => {
  const USER = /(?:^|[\s_-])(user|human|outgoing|self|me|sent|question|request)(?:[\s_-]|$)/i;
  const BOT  = /(?:^|[\s_-])(bot|assistant|agent|incoming|received|answer|response|reply|operator)(?:[\s_-]|$)/i;
  const isUser = (node) => {
    let n = node;
    for (let i = 0; i < 6 && n; i++, n = n.parentElement) {
      let cls = '';
      try { cls = typeof n.className === 'string' ? n.className
                  : ((n.getAttribute && n.getAttribute('class')) || ''); } catch (e) {}
      let attrs = '';
      if (n.getAttribute) {
        attrs = [n.getAttribute('data-message-author-role'),
                 n.getAttribute('data-author'),
                 n.getAttribute('data-role'),
                 n.getAttribute('data-from'),
                 n.getAttribute('role')].filter(Boolean).join(' ');
      }
      const blob = cls + ' ' + attrs;
      if (BOT.test(blob)) return false;
      if (USER.test(blob)) return true;
    }
    return false;
  };
  // Collect candidate elements (skip user-authored bubbles).
  const cands = [];
  const seen = new Set();
  for (const sel of selectors) {
    let els;
    try { els = document.querySelectorAll(sel); } catch (e) { continue; }
    for (const el of els) {
      if (seen.has(el)) continue;
      seen.add(el);
      if (isUser(el)) continue;
      cands.push(el);
    }
  }
  // Keep only INNERMOST matches: drop any element that contains another
  // candidate. This prevents a conversation *container* (which also matches a
  // broad selector) from being captured as one giant blob of the whole chat —
  // we want the individual message bubbles, not their wrapper.
  const candSet = new Set(cands);
  const leaves = cands.filter((el) => {
    for (const other of candSet) {
      if (other !== el && el.contains(other)) return false;
    }
    return true;
  });
  const out = [];
  for (const el of leaves) {
    const t = (el.innerText || '').trim();
    if (t) out.push(t);
  }
  return out;
}
"""


def _last_user_text(messages: List[Dict[str, Any]]) -> Optional[str]:
    """Return the text of the last user message in ``messages``."""
    for msg in reversed(messages or []):
        if (msg or {}).get("role") != "user":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text = part.get("text")
                    if isinstance(text, str):
                        return text
    return None


def _norm_ws(text: str) -> str:
    """Collapse all whitespace runs to single spaces and strip."""
    return re.sub(r"\s+", " ", text or "").strip()


def _looks_like_prompt_echo(candidate: str, prompt: str) -> bool:
    """Whether ``candidate`` is the user's prompt echoed back by the widget.

    Whitespace-insensitive (chat UIs reflow newlines), and tolerant of the
    widget clipping a long prompt: matches exact, either-way containment, or a
    substantial shared leading run (truncated echo, possibly with an ellipsis).
    """
    c = _norm_ws(candidate)
    p = _norm_ws(prompt)
    if not p:
        return False
    if c == p or p in c or c in p:
        return True
    # Truncated echo: require a long shared prefix so short genuine replies
    # (e.g. a one-line refusal) are never mistaken for the echo.
    k = min(len(c), len(p))
    return k >= 60 and c[:k] == p[:k]


def _new_reply(
    before: List[str],
    after: List[str],
    prompt: str,
    sent_prompts: Optional[List[str]] = None,
) -> Optional[str]:
    """Pick the new assistant message from message-text snapshots.

    ``before``/``after`` are the visible message texts before and after sending.
    The new texts are those in ``after`` not already in ``before``; any text
    matching one of the ``sent_prompts`` (all user messages typed so far, not
    just the current one) is dropped so that in multi-turn conversations a
    previous user bubble that re-appears in the snapshot is never returned as
    the bot's reply.  The last remaining non-empty text is the freshest
    assistant turn.  ``None`` if nothing new qualifies.
    """
    before_counts: Dict[str, int] = {}
    for t in before:
        before_counts[t] = before_counts.get(t, 0) + 1

    # All prompts we've ever sent — current plus any prior turns.
    all_sent: List[str] = sent_prompts if sent_prompts else [prompt]

    new_texts: List[str] = []
    for t in after:
        if before_counts.get(t, 0) > 0:
            before_counts[t] -= 1  # consume one occurrence that already existed
            continue
        stripped = t.strip()
        if not stripped:
            continue
        # Drop any text that is a user prompt (current or from earlier turns).
        if any(_looks_like_prompt_echo(stripped, p) for p in all_sent):
            continue
        new_texts.append(stripped)
    return new_texts[-1] if new_texts else None


_WEB_AGENT_CUSTOM_LLM_CLASS = None


def _get_web_agent_custom_llm_class():
    """Lazily build the CustomLLM subclass once litellm is importable."""
    global _WEB_AGENT_CUSTOM_LLM_CLASS
    if _WEB_AGENT_CUSTOM_LLM_CLASS is not None:
        return _WEB_AGENT_CUSTOM_LLM_CLASS

    from litellm import CustomLLM
    from litellm.types.utils import ModelResponse

    class _BrowserSession:
        """A persistent Playwright page driven prompt-by-prompt.

        Started lazily on first send and kept open for the agent's lifetime so
        conversation state accumulates like a real chat. All sends are
        serialized (one shared page is not concurrency-safe).
        """

        def __init__(
            self,
            *,
            url: str,
            headless: bool,
            timeout: int,
            wait_after_send: float,
            settle_ms: int,
            input_selector: Optional[str],
            reply_selector: Optional[str],
            launcher_selector: Optional[str],
            dismiss_consent: bool,
            llm_fallback_model: Optional[str],
            install_browser: bool,
            log,
        ):
            self.url = url
            self.headless = headless
            self.timeout = timeout
            self.wait_after_send = wait_after_send
            self.settle_ms = settle_ms
            self.install_browser = install_browser
            self.input_selector = input_selector
            self.reply_selector = reply_selector
            self.launcher_selector = launcher_selector
            self.dismiss_consent = dismiss_consent
            self.llm_fallback_model = llm_fallback_model
            self.logger = log
            self._lock = threading.Lock()
            self._started = False
            self._pw_ctx = None
            self._browser = None
            self._page = None
            self._input = None
            self._frame = None
            # Playwright's sync API binds every object to the thread that
            # created it. Attacks run goals on thread-pool workers, so we pin
            # ALL browser work to one dedicated thread and marshal calls to it.
            self._executor = None
            # All prompts typed across turns.  Used by _wait_for_reply so that
            # in multi-turn conversations previous user bubbles are never
            # mistaken for the bot's reply.
            self._sent_prompts: List[str] = []

        # ---- single-thread marshalling -----------------------------------

        def _ensure_executor(self):
            if self._executor is None:
                from concurrent.futures import ThreadPoolExecutor

                self._executor = ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix="web-session"
                )

        def _run(self, fn):
            """Run ``fn`` on the dedicated Playwright thread, return its result.

            Must NOT be called from within that thread itself (single worker →
            self-submit would deadlock); internal helpers call each other
            directly instead.
            """
            self._ensure_executor()
            return self._executor.submit(fn).result()

        # ---- lifecycle ---------------------------------------------------

        def _start(self) -> None:
            from hackagent.router.discovery.browser import (
                _dismiss_consent,
                _find_input,
                _open_chat_launcher,
                ensure_chromium,
            )

            ensure_chromium(auto_install=self.install_browser)
            from playwright.sync_api import sync_playwright

            self._pw_ctx = sync_playwright()
            pw = self._pw_ctx.__enter__()
            self._browser = pw.chromium.launch(headless=self.headless)
            context = self._browser.new_context()
            self._page = context.new_page()
            self._page.goto(
                self.url, wait_until="domcontentloaded", timeout=self.timeout * 1000
            )
            self._page.wait_for_timeout(self.settle_ms)
            # Accept/dismiss a cookie-consent banner first — it commonly overlays
            # the page and would intercept clicks on the chat launcher.
            if self.dismiss_consent:
                try:
                    if _dismiss_consent(self._page):
                        self.logger.info("🍪 dismissed a cookie-consent banner")
                        self._page.wait_for_timeout(self.settle_ms)
                except Exception:
                    pass
            # The chat box on SPAs often hydrates a beat after load — poll for it
            # for a few seconds rather than giving up on the first miss. Many
            # sites also keep the bot collapsed behind a launcher bubble (often
            # in an iframe); if no input shows up, click the launcher to reveal
            # the widget, then keep polling (frames update after the click).
            launched = False
            for attempt in range(20):
                self._input, self._frame = _find_input(self._page, self.input_selector)
                if self._input is not None:
                    break
                # Try opening the widget early, then retry a couple more times
                # in case the first click didn't take or it loaded in a frame.
                if attempt in (1, 6, 11):
                    if _open_chat_launcher(self._page, self.launcher_selector):
                        launched = True
                        self._page.wait_for_timeout(self.settle_ms)
                        continue
                self._page.wait_for_timeout(500)
            if self._input is None:
                # Collect a diagnostic from the LIVE DOM before tearing down —
                # JS-injected widgets are invisible to static fetches, so this
                # is the only place the real selectors are observable.
                diag = self._page_diagnostics()
                # Runs on the session thread already — tear down inline (routing
                # through the executor here would self-deadlock).
                self._close_browser()
                hint = (
                    "pass --input-selector / --reply-selector with the box's CSS "
                    "selector, --open-selector to click the chat launcher first "
                    "(inspect them in devtools), or run --headed to watch"
                )
                if self.input_selector:
                    hint = (
                        f"the --input-selector {self.input_selector!r} matched "
                        "nothing visible; check it in devtools, or run --headed"
                    )
                elif launched:
                    hint = (
                        "clicked a chat launcher but still found no input — the "
                        "widget may need --open-selector / --input-selector, or "
                        "run --headed to watch"
                    )
                msg = f"Loaded {self.url} but could not locate a chat input ({hint})."
                if diag:
                    msg += f"\nOn-page candidates seen — {diag}"
                raise WebAgentInteractionError(msg)
            self._started = True
            atexit.register(self.close)

        def _page_diagnostics(self, limit: int = 12) -> str:
            """Best-effort summary of chat-like elements + iframes on the live page.

            JS-injected chat widgets aren't visible to static fetches, so when
            input-location fails this surfaces what's actually on the rendered
            page — concrete `id`/`class`/`aria-label`s and iframe URLs the user
            can turn into `--open-selector` / `--input-selector`. Fully guarded:
            never raises (it runs on an already-failing path).
            """
            keywords = (
                "chat",
                "bot",
                "assist",
                "help",
                "widget",
                "messag",
                "launcher",
                "support",
                "agent",
            )
            found: List[str] = []
            iframe_urls: List[str] = []
            try:
                frames = list(self._page.frames)
            except Exception:
                return ""
            for frame in frames:
                try:
                    furl = frame.url
                except Exception:
                    furl = ""
                if (
                    furl
                    and furl.startswith("http")
                    and furl.rstrip("/") != self.url.rstrip("/")
                ):
                    if furl not in iframe_urls:
                        iframe_urls.append(furl)
                for sel in ("button", "[role=button]", "a", "textarea", "input"):
                    if len(found) >= limit:
                        break
                    try:
                        els = frame.query_selector_all(sel)
                    except Exception:
                        continue
                    for el in els:
                        if len(found) >= limit:
                            break
                        try:
                            if not el.is_visible():
                                continue
                            eid = el.get_attribute("id") or ""
                            cls = el.get_attribute("class") or ""
                            aria = el.get_attribute("aria-label") or ""
                            txt = (el.inner_text() or "").strip()
                            blob = " ".join((eid, cls, aria, txt)).lower()
                            if not any(k in blob for k in keywords):
                                continue
                            desc = sel.strip("[]").split("=")[0]
                            if eid:
                                desc += f"#{eid}"
                            elif cls:
                                desc += "." + ".".join(cls.split()[:2])
                            label = (aria or txt)[:40]
                            if label:
                                desc += f"  [{label}]"
                            if desc not in found:
                                found.append(desc)
                        except Exception:
                            continue
            parts: List[str] = []
            if found:
                parts.append("chat-like elements: " + " ; ".join(found))
            if iframe_urls:
                parts.append("iframes: " + ", ".join(iframe_urls[:5]))
            return "  ".join(parts)

        def _close_browser(self) -> None:
            """Tear down Playwright objects. Must run on the session thread."""
            try:
                if self._browser is not None:
                    self._browser.close()
            except Exception:
                pass
            try:
                if self._pw_ctx is not None:
                    self._pw_ctx.__exit__(None, None, None)
            except Exception:
                pass
            self._browser = None
            self._pw_ctx = None
            self._started = False

        def close(self) -> None:
            # Browser teardown is a Playwright call, so it must happen on the
            # session thread. Route it through the executor, then shut the
            # executor down. Safe to call from any thread (incl. atexit).
            executor = self._executor
            if executor is not None:
                try:
                    executor.submit(self._close_browser).result(timeout=30)
                except Exception:
                    pass
                executor.shutdown(wait=False)
                self._executor = None
            else:
                self._close_browser()

        # ---- DOM helpers -------------------------------------------------

        def _message_texts(self) -> List[str]:
            # Explicit reply_selector → trust it verbatim (the user pinned the
            # bot's bubble), no user/assistant heuristics.
            if self.reply_selector:
                texts: List[str] = []
                for frame in self._page.frames:
                    try:
                        elements = frame.query_selector_all(self.reply_selector)
                    except Exception:
                        continue
                    for el in elements:
                        try:
                            t = el.inner_text().strip()
                        except Exception:
                            continue
                        if t:
                            texts.append(t)
                return texts

            # Heuristic: one evaluate per frame, excluding user-authored bubbles.
            texts = []
            for frame in self._page.frames:
                try:
                    frame_texts = frame.evaluate(
                        _MESSAGE_EXTRACT_JS, list(_MESSAGE_SELECTORS)
                    )
                except Exception:
                    continue
                if isinstance(frame_texts, list):
                    for t in frame_texts:
                        if isinstance(t, str) and t.strip():
                            texts.append(t.strip())
            return texts

        def _wait_for_reply(self, before: List[str], prompt: str) -> Optional[str]:
            """Poll the DOM until a new assistant reply appears and stops growing."""
            deadline_polls = max(1, int(self.wait_after_send / 0.4))
            last = None
            stable = 0
            for _ in range(deadline_polls + 8):
                self._page.wait_for_timeout(400)
                reply = _new_reply(
                    before, self._message_texts(), prompt, self._sent_prompts
                )
                if reply and reply == last:
                    stable += 1
                    if stable >= 2:  # unchanged for ~0.8s → streaming settled
                        return reply
                else:
                    stable = 0
                last = reply
            return last

        def _llm_extract_reply(self, prompt: str) -> Optional[str]:
            """Last resort: ask an LLM to read the reply from the page text."""
            if not self.llm_fallback_model:
                return None
            litellm, available = _get_litellm()
            if not available:
                return None
            try:
                page_text = self._page.inner_text("body")[:6000]
            except Exception:
                return None
            try:
                resp = litellm.completion(
                    model=self.llm_fallback_model,
                    messages=[
                        {
                            "role": "system",
                            "content": "Extract ONLY the assistant chatbot's most "
                            "recent reply from this page text. Output just that "
                            "reply, nothing else.",
                        },
                        {
                            "role": "user",
                            "content": f"User asked: {prompt}\n\nPage text:\n{page_text}",
                        },
                    ],
                    temperature=0,
                    max_tokens=800,
                )
                return (resp.choices[0].message.content or "").strip() or None
            except Exception as e:
                self.logger.debug("web-agent LLM reply fallback failed: %s", e)
                return None

        # ---- send --------------------------------------------------------

        def ready(self) -> None:
            """Start the session (load page, dismiss consent, open the widget,
            locate the input) WITHOUT sending a message.

            Used for non-invasive reachability checks so preflight doesn't type a
            junk message into a live person-facing chatbot (which would pollute
            the real conversation and the captured transcript). Raises
            WebAgentInteractionError if the chat input can't be located.
            """
            with self._lock:
                self._run(self._start_if_needed)

        def _start_if_needed(self) -> bool:
            if not self._started:
                self._start()
            return True

        def send(self, prompt: str) -> str:
            # Serialize callers, then run the actual browser work on the single
            # dedicated Playwright thread (sync API is thread-bound).
            with self._lock:
                return self._run(lambda: self._send_locked(prompt))

        def _send_locked(self, prompt: str) -> str:
            from hackagent.router.discovery.browser import (
                _find_send_button,
                _type_into,
            )

            if not self._started:
                self._start()

            before = self._message_texts()
            try:
                _type_into(self._input, prompt)
                # Read back the text the browser actually accepted — input
                # fields may strip or transform certain characters (e.g.
                # non-printable ASCII produced by BoN ascii_perturbation).
                # Using the sanitised text for echo-detection ensures we never
                # mistake the echoed user bubble for the bot's reply.
                try:
                    typed_prompt = self._input.input_value().strip() or prompt
                except Exception:
                    typed_prompt = prompt
                # Register the prompt BEFORE pressing Enter so that as soon as
                # the user bubble appears in the DOM it is already in the
                # sent_prompts filter (multi-turn safety).
                self._sent_prompts.append(typed_prompt)
                self._input.press("Enter")
            except Exception as e:
                raise WebAgentInteractionError(
                    f"Failed to enter the prompt: {e}"
                ) from e

            reply = self._wait_for_reply(before, typed_prompt)
            if reply is None:
                # Try a send button, then poll again.
                btn = _find_send_button(self._frame)
                if btn is not None:
                    try:
                        btn.click()
                    except Exception:
                        pass
                    reply = self._wait_for_reply(before, typed_prompt)
            if reply is None:
                reply = self._llm_extract_reply(prompt)
            if reply is None:
                raise WebAgentInteractionError(
                    "Sent the prompt but could not read a reply from the page. "
                    "Pass a 'reply_selector', set 'llm_fallback_model', or run "
                    "headless=False to inspect the widget."
                )
            return reply

    class _WebAgentCustomLLM(CustomLLM):
        """CustomLLM handler that drives a live browser page per prompt."""

        def __init__(self, *, session: "_BrowserSession", model: str, log):
            super().__init__()
            self.session = session
            self.model = model
            self.logger = log

        def completion(self, *args, **kwargs):
            messages = kwargs.get("messages") or []
            model_response: ModelResponse = (
                kwargs.get("model_response") or ModelResponse()
            )
            prompt_text = _last_user_text(messages)
            if not prompt_text:
                raise WebAgentInteractionError(
                    "Web agent requires at least one user message with text content."
                )
            self.logger.info("🌐 web-agent: driving live page")
            reply = self.session.send(prompt_text)

            model_response.choices[0].message.content = reply  # type: ignore[attr-defined]
            try:
                model_response.choices[0].finish_reason = "stop"  # type: ignore[attr-defined]
            except Exception:
                pass
            model_response.model = kwargs.get("model") or self.model
            return model_response

        async def acompletion(self, *args, **kwargs):
            import asyncio

            return await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.completion(*args, **kwargs)
            )

    _WebAgentCustomLLM._session_cls = _BrowserSession  # type: ignore[attr-defined]
    _WEB_AGENT_CUSTOM_LLM_CLASS = _WebAgentCustomLLM
    return _WebAgentCustomLLM


class WebAgent(Agent):
    """
    Adapter that red-teams a website's chatbot by driving the live page.

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
          banner on load so it can't intercept clicks on the chat launcher.
        - ``llm_fallback_model``: LiteLLM model used to read the reply only when
          the heuristics find nothing.
    """

    ADAPTER_TYPE = "WebAgent"

    def __init__(self, id: str, config: Dict[str, Any]):
        url = config.get("url") or config.get("endpoint")
        if not url:
            raise WebAgentConfigurationError(
                f"Missing required configuration key 'url' for WebAgent: {id}"
            )

        super().__init__(id, config)
        self._init_generation_params()

        self.url: str = str(url)
        self.name: str = config.get("name") or self._host_of(self.url)
        self.model_name = self.name
        self.headless: bool = bool(config.get("headless", True))
        self.timeout: int = int(config.get("timeout", 30))
        self.wait_after_send: float = float(config.get("wait_after_send", 20))
        self.settle_ms: int = int(config.get("settle_ms", 1500))
        self.input_selector: Optional[str] = config.get("input_selector")
        self.reply_selector: Optional[str] = config.get("reply_selector")
        self.launcher_selector: Optional[str] = config.get("launcher_selector")
        self.dismiss_consent: bool = bool(config.get("dismiss_consent", True))
        self.llm_fallback_model: Optional[str] = config.get("llm_fallback_model")
        self.install_browser: bool = bool(config.get("install_browser", True))

        self._provider_name = f"{_WEB_PROVIDER_PREFIX}_{id}"
        self.litellm_model = f"{self._provider_name}/{self._slug(self.name)}"
        self.api_base_url: Optional[str] = None
        self.actual_api_key: Optional[str] = None
        self.default_thinking = None
        self.default_tools = None
        self.default_tool_choice = None
        self.default_extra_body = None

        self._register_custom_provider()
        self.logger.info(
            f"WebAgent '{self.id}' registered as LiteLLM provider "
            f"'{self._provider_name}' driving {self.url}"
        )

    @staticmethod
    def _host_of(url: str) -> str:
        from urllib.parse import urlparse

        return urlparse(url).netloc or url

    @staticmethod
    def _slug(text: str) -> str:
        import re

        slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", text).strip("-")
        return slug or "web"

    def _register_custom_provider(self) -> None:
        litellm, available = _get_litellm()
        if not available:
            raise WebAgentConfigurationError(
                "litellm is required for WebAgent but is not installed."
            )

        handler_cls = _get_web_agent_custom_llm_class()
        session = handler_cls._session_cls(  # type: ignore[attr-defined]
            url=self.url,
            headless=self.headless,
            timeout=self.timeout,
            wait_after_send=self.wait_after_send,
            settle_ms=self.settle_ms,
            input_selector=self.input_selector,
            reply_selector=self.reply_selector,
            launcher_selector=self.launcher_selector,
            dismiss_consent=self.dismiss_consent,
            llm_fallback_model=self.llm_fallback_model,
            install_browser=self.install_browser,
            log=self.logger,
        )
        handler = handler_cls(
            session=session, model=self.litellm_model, log=self.logger
        )

        provider = self._provider_name
        litellm.custom_provider_map = [
            entry
            for entry in litellm.custom_provider_map
            if entry.get("provider") != provider
        ]
        litellm.custom_provider_map.append(
            {"provider": provider, "custom_handler": handler}
        )
        if provider not in litellm._custom_providers:
            litellm._custom_providers.append(provider)
        self._custom_handler = handler

    def probe_ready(self) -> Optional[str]:
        """Non-invasive reachability check for preflight.

        Starts the browser session and confirms the chat input is locatable
        WITHOUT sending a message — so the availability probe never types a
        junk "healthcheck" into the live chatbot (which would contaminate the
        real conversation and the recorded transcript). Returns None when the
        widget is reachable, or an error string otherwise.
        """
        try:
            self._custom_handler.session.ready()
            return None
        except Exception as exc:
            return f"{type(exc).__name__}: {exc}"

    def handle_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Send a single turn to the live page via ``litellm.completion``."""
        is_valid, prompt_text, messages = self._validate_request(request_data)
        if not is_valid:
            return self._build_error_response(
                error_message=(
                    "Request data must include either 'messages' or 'prompt' field."
                ),
                status_code=400,
                raw_request=request_data,
            )
        if not messages:
            messages = self._prompt_to_messages(prompt_text)  # type: ignore[arg-type]

        litellm, available = _get_litellm()
        if not available:
            return self._build_error_response(
                error_message="litellm is not installed",
                status_code=500,
                raw_request=request_data,
            )

        try:
            response = litellm.completion(model=self.litellm_model, messages=messages)
        except Exception as exc:
            self.logger.exception(
                f"Web agent litellm dispatch failed for agent {self.id}: {exc}"
            )
            return self._build_error_response(
                error_message=(
                    f"{self.ADAPTER_TYPE} error ({type(exc).__name__}): {exc}"
                ),
                status_code=500,
                raw_request=request_data,
            )

        text = _envelope.extract_text_from_response(
            response, model_name=self.litellm_model
        )
        if isinstance(text, str) and text.startswith("[GENERATION_ERROR:"):
            return self._build_error_response(
                error_message=f"{self.ADAPTER_TYPE} generation error: {text}",
                status_code=500,
                raw_request=request_data,
            )

        agent_specific_data = _envelope.build_agent_specific_data(
            model_name=self.litellm_model,
            invoked_parameters={"url": self.url, "live_browser": True},
        )
        return self._build_success_response(
            processed_response=text,
            raw_request=request_data,
            raw_response_body=response,
            agent_specific_data=agent_specific_data,
        )
