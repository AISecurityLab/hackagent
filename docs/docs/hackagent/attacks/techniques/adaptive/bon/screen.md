---
sidebar_label: screen
title: hackagent.attacks.techniques.adaptive.bon.screen
---

The reference&#x27;s guards against classifier false positives.

Ported from `bon/attacks/run_text_bon.py` in jplhughes/bon-jailbreaking
(MIT, Copyright (c) 2024 Anthropic), described in Appendix B.1 of the paper.
Augmented prompts often get replies that restate the request, are too short
to help, or try to decode the noise instead of answering; a grader tends to
call those harmful, so the reference never counts them as jailbreaks.

#### FALSE\_POSITIVE\_PHRASES

Phrases that mark a reply decoding the augmented prompt instead of
complying with it. Copied verbatim from the reference.

#### too\_short

```python
def too_short(goal: str, reply: str, min_extra_words: int) -> bool
```

Whether the reply is too close in length to the request to grade.

The reference skips the grader for these: such a reply mostly restates
the request.

#### not\_counted

```python
def not_counted(reply: str, min_words: int) -> Optional[str]
```

Why a reply the grader called harmful is still not a jailbreak, if so.

