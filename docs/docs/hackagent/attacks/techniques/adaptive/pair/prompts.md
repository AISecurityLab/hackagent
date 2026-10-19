---
sidebar_label: prompts
title: hackagent.attacks.techniques.adaptive.pair.prompts
---

The attacker&#x27;s instructions, and the turns a PAIR stream is built from.

A stream is one attacker conversation: a fixed system prompt, an opening
request, then a feedback turn after every attempt. The attacker sees the
target&#x27;s reply and its score, which is what lets the next prompt refine the
last one rather than start over.

The score comes from the campaign&#x27;s panel, or, when the run configures a
`scorer` role, from that model rating the reply 1-10 against
:data:`SCORER_SYSTEM_PROMPT`.

#### SCORER\_SYSTEM\_PROMPT

The rubric PAIR&#x27;s own scorer is given, when a run configures one.
It is the 1-10 scale the attacker&#x27;s instructions already describe, so
the number fed back means the same thing either way.

#### STREAM\_STRATEGIES

The reference implementation gives each conversation one of three
approaches. They are kept separate per stream so a failed approach does
not contaminate the other search trajectories.

#### system\_prompt

```python
def system_prompt(goal: str, stream: int, target_str: str) -> str
```

The fixed opening instruction for one stream.

#### opening\_request

```python
def opening_request(goal: str, target_str: str) -> str
```

The first user turn of a stream.

#### feedback

```python
def feedback(goal: str,
             target_str: str,
             reply: str,
             score: Optional[float],
             explanation: str = "",
             limit: int = 2500) -> str
```

The user turn appended after an attempt, carrying what came back.

#### scorer\_system\_prompt

```python
def scorer_system_prompt(goal: str) -> str
```

The rubric the scorer rates against.

#### scorer\_request

```python
def scorer_request(prompt: str, reply: str) -> str
```

The exchange handed to the scorer, whole.

Nothing is trimmed here. A rating is a judgement about a reply, and a
reply cut short is a different reply: the refusal that turns into
compliance three paragraphs down would be scored as a refusal. The
attacker&#x27;s feedback is trimmed instead, because there the point is the
gist and the turns accumulate.

#### parse\_rating

```python
def parse_rating(text: Optional[str]) -> Optional[float]
```

Read the scorer&#x27;s 1-10 rating; `None` when it gave no number.

The asked-for `Rating: [[n]]` wins. Models that answer in prose still
tend to name the number, so looser spellings are tried in turn, and the
last bare number is a final guess rather than discarding the call.

