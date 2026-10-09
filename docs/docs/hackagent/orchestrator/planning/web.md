---
sidebar_label: web
title: hackagent.orchestrator.planning.web
---

Targets for live-browser chatbots.

#### build\_web\_target

```python
def build_web_target(
        url: str,
        *,
        name: Optional[str] = None,
        headless: bool = True,
        input_selector: Optional[str] = None,
        reply_selector: Optional[str] = None,
        launcher_selector: Optional[str] = None,
        dismiss_consent: bool = True,
        llm_fallback_model: Optional[str] = None,
        timeout: Optional[int] = None) -> Tuple[str, Dict[str, Any]]
```

Build the `(&quot;web&quot;, operational_config)` target for a live-browser chatbot.

