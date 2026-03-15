---
sidebar_label: generation
title: hackagent.attacks.techniques.bon.generation
---

Best-of-N (BoN) generation module.

Core algorithm: for each goal, run ``n_steps`` sequential search steps.
Within each step, generate ``num_concurrent_k`` independently-seeded
augmented variants of the prompt and send them to the target model in
parallel.  After selecting the best candidate (longest response), a
**judge evaluator** is called to determine whether the candidate constitutes
a successful jailbreak.  If the judge confirms success, the search stops
early.  If no step produces a jailbreak after all steps, the attack is
marked as failed.

Text augmentations ported from the original BoN codebase:
- **word_scrambling**: shuffles middle characters of words &gt;3 chars
- **random_capitalization**: randomly toggles letter case
- **ascii_perturbation**: shifts printable ASCII chars by ±1

Based on: https://arxiv.org/abs/2412.03556

## \_StepJudge Objects

```python
class _StepJudge()
```

Lightweight wrapper to call one or more judges on a single candidate.

Instantiated once per :func:`execute` call (not per step) and re-used
throughout the generation loop to avoid repeated router creation.

#### available

```python
@property
def available() -> bool
```

True if at least one judge was successfully initialised.

#### is\_jailbreak

```python
def is_jailbreak(goal: str, augmented_prompt: str,
                 response: str) -> Tuple[bool, float, Dict[str, Any]]
```

Evaluate a single candidate with all judges.

**Returns**:

  ``(is_success, best_score, judge_columns)`` where
  *judge_columns* contains the raw eval/explanation columns
  produced by each judge.

#### apply\_word\_scrambling

```python
def apply_word_scrambling(text: str, sigma: float) -> str
```

Scramble middle characters of words longer than 3 characters.

For each qualifying word, the first and last characters are preserved
while the middle characters are randomly shuffled.

**Arguments**:

- `text` - Input text to augment.
- `sigma` - Base augmentation strength.  Scrambling probability per word
  is ``sigma^(1/2)``.
  

**Returns**:

  Augmented text with scrambled words.
  
  Example::
  
  apply_word_scrambling(&quot;The quick brown fox&quot;, 0.4)
  # possible: &quot;The qiuck bwron fox&quot;

#### apply\_random\_capitalization

```python
def apply_random_capitalization(text: str, sigma: float) -> str
```

Randomly toggle letter case for each character.

**Arguments**:

- `text` - Input text to augment.
- `sigma` - Base augmentation strength.  Toggle probability per character
  is ``sigma^(1/2)``.
  

**Returns**:

  Augmented text with random case changes.
  
  Example::
  
  apply_random_capitalization(&quot;hello world&quot;, 0.4)
  # possible: &quot;hEllo wOrLd&quot;

#### apply\_ascii\_noising

```python
def apply_ascii_noising(text: str, sigma: float) -> str
```

Shift printable ASCII characters by ±1 code point.

**Arguments**:

- `text` - Input text to augment.
- `sigma` - Base augmentation strength.  Perturbation probability per
  character is ``sigma^3``.
  

**Returns**:

  Augmented text with ASCII perturbations.
  
  Example::
  
  apply_ascii_noising(&quot;hello world&quot;, 0.4)
  # possible: &quot;hfllo world&quot;

#### augment\_text

```python
def augment_text(text: str,
                 sigma: float,
                 seed: int,
                 word_scrambling: bool = True,
                 random_capitalization: bool = True,
                 ascii_perturbation: bool = True) -> str
```

Apply all enabled text augmentations to *text*.

Sets the random seed for reproducibility, then applies augmentations in
the canonical order: word scrambling → random capitalization → ASCII
perturbation.

**Arguments**:

- `text` - The original prompt text to augment.
- `sigma` - Augmentation strength parameter (0–1).
- `seed` - Random seed for reproducibility.
- `word_scrambling` - Enable word-scrambling augmentation.
- `random_capitalization` - Enable random-capitalization augmentation.
- `ascii_perturbation` - Enable ASCII-perturbation augmentation.
  

**Returns**:

  Augmented text.

#### execute

```python
def execute(goals: List[str], agent_router: AgentRouter,
            config: Dict[str, Any], logger: logging.Logger) -> List[Dict]
```

Generate augmented prompts, execute them, and judge inline.

For each goal, performs a multi-step search:

1. For each step ``n`` in ``[0, n_steps)``:
a. Generate ``num_concurrent_k`` augmented candidates (different seeds).
b. Send all candidates to the target model in parallel.
c. Select the best candidate (longest response).
d. **Call the judge** on the best candidate.
e. If the judge confirms a jailbreak → **early stop**.
2. After all steps, if no jailbreak was found, mark as failed.

**Arguments**:

- `goals` - List of harmful prompt strings.
- `agent_router` - Router for target model communication.
- `config` - Configuration dictionary with ``bon_params``, ``judges``, etc.
- ``3 - Logger instance.
  

**Returns**:

  List of dicts (one per goal) with keys: ``goal``, ``augmented_prompt``,
  ``response``, ``error``, ``step``, ``candidate``, ``seed``,
  ``augmentation_params``, ``best_score``, ``success``,
  ``generation_elapsed_s``, plus any judge columns.

