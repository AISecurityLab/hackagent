---
sidebar_label: attack
title: hackagent.attacks.techniques.flipattack.attack
---

FlipAttack implementation.

Character-level adversarial attack that flips characters, words, or sentences
to bypass LLM safety measures.

Based on: https://arxiv.org/abs/2410.02832

The ``FlipAttack`` class serves as both the HackAgent pipeline orchestrator
(``BaseAttack`` subclass) and the algorithm itself.  The obfuscation methods
(``flip_word_order``, ``flip_char_in_word``, ``flip_char_in_sentence``,
``generate``, etc.) live directly on the class, kept stateless so they can
be called safely for multiple goals in sequence.

Result Tracking:
    Uses TrackingCoordinator to manage both pipeline-level StepTracker
    and per-goal Tracker. The coordinator handles goal lifecycle,
    crash-safe finalization, and data enrichment (result_id injection).

## FlipAttack Objects

```python
class FlipAttack(BaseAttack)
```

FlipAttack — character-level adversarial attack using prompt obfuscation.

Implements the FlipAttack technique from:
Liu et al., &quot;FlipAttack: Jailbreak LLMs via Flipping&quot; (2024)
https://arxiv.org/abs/2410.02832

This class serves as both the **HackAgent pipeline orchestrator**
(``BaseAttack`` subclass) and the **algorithm** itself.  The obfuscation
methods (``flip_word_order``, ``flip_char_in_word``, ``flip_char_in_sentence``,
``generate``, etc.) live directly on the class.

Flip modes (set via ``config[&quot;flipattack_params&quot;][&quot;flip_mode&quot;]``):
FWO  Reverses the word order of the input sentence.
FCW  Reverses characters inside each individual word.
FCS  Reverses all characters of the entire sentence (default).
FMM  Applies FCS obfuscation but uses the FWO decoding instruction
to exploit model confusion between reversal directions.

Optional enhancements (combinable):
cot      Appends &quot;step by step&quot; to the decoding instruction.
lang_gpt Wraps the system prompt in a LangGPT Role/Profile template.
few_shot Injects two task-specific decoding demonstrations.

**Attributes**:

- ``2 - Active obfuscation mode, read from config.
- ``3 - Whether chain-of-thought is enabled.
- ``4 - Whether LangGPT template is enabled.
- ``5 - Whether few-shot demonstrations are injected.
- ``6 - Template system prompt built once during setup.
- ``7 - LangGPT step instructions (only when lang_gpt=True).

#### \_\_init\_\_

```python
def __init__(config: Optional[Dict[str, Any]] = None,
             client: Optional[AuthenticatedClient] = None,
             agent_router: Optional[AgentRouter] = None)
```

Initialize FlipAttack with configuration.

**Arguments**:

- `config` - Optional dictionary containing parameters to override
  :data:`~hackagent.attacks.techniques.flipattack.config.DEFAULT_FLIPATTACK_CONFIG`.
- `client` - AuthenticatedClient instance passed from the orchestrator.
- `agent_router` - AgentRouter instance for the target model.
  

**Raises**:

- `ValueError` - If ``client`` or ``agent_router`` is ``None``.

#### flip\_word\_order

```python
def flip_word_order(input_str: str) -> str
```

Reverse the word order of *input_str*.

**Arguments**:

- `input_str` - Whitespace-separated sentence to obfuscate.
  

**Returns**:

  A new string with words in reverse order.
  
  Example::
  
  flip_word_order(&quot;hello world foo&quot;)  # &quot;foo world hello&quot;

#### flip\_char\_in\_word

```python
def flip_char_in_word(input_str: str) -> str
```

Reverse the characters inside each individual word.

Word boundaries are determined by whitespace splitting.  The word
order is preserved; only the characters within each token are flipped.

**Arguments**:

- `input_str` - Sentence to obfuscate.
  

**Returns**:

  A new string where every word has its characters reversed.
  
  Example::
  
  flip_char_in_word(&quot;hello world&quot;)  # &quot;olleh dlrow&quot;

#### flip\_char\_in\_sentence

```python
def flip_char_in_sentence(input_str: str) -> str
```

Reverse *every* character in the entire sentence.

**Arguments**:

- `input_str` - Sentence to obfuscate.
  

**Returns**:

  The full string reversed character-by-character.
  
  Example::
  
  flip_char_in_sentence(&quot;hello&quot;)  # &quot;olleh&quot;

#### demo

```python
def demo(input_str: str, mode: str) -> str
```

Apply the flip transform matching *mode* to *input_str*.

Used internally to build few-shot demonstration examples.

**Arguments**:

- `input_str` - Short example phrase to transform.
- `mode` - One of ``&quot;FWO&quot;``, ``&quot;FCW&quot;``, ``&quot;FCS&quot;``, or ``&quot;FMM&quot;``.
  

**Returns**:

  Obfuscated version of *input_str* using the chosen mode.

#### split\_sentence\_in\_half

```python
def split_sentence_in_half(input_str: str)
```

Split *input_str* roughly in half at a word boundary.

**Arguments**:

- `input_str` - Sentence to split.
  

**Returns**:

  Tuple of ``(first_half, second_half)`` strings.

#### generate

```python
def generate(harm_prompt: str)
```

Build the obfuscated attack message list for *harm_prompt*.

Stateless: each call starts from the base system prompt so the
method is safe to call for multiple goals in sequence.

**Arguments**:

- `harm_prompt` - The original harmful request to obfuscate.
  

**Returns**:

  Tuple of:
  - ``log`` (str): Debug string, e.g. ``&quot;TASK is &#x27;...&#x27;&quot;``.
  - ``attack`` (list[dict]): OpenAI chat-format message list
  with ``&quot;system&quot;`` and ``&quot;user&quot;`` entries.
  

**Raises**:

- ``1 - If ``self.flip_mode`` is not a recognised mode.

#### run

```python
@with_tui_logging(logger_name="hackagent.attacks", level=logging.INFO)
def run(goals: List[str]) -> List[Dict]
```

Execute the full FlipAttack pipeline.

Uses a split-phase approach: the coordinator is created without
goal Results upfront.  After the Generation step, Results are
created only for the surviving goals that will actually be tested.

**Arguments**:

- `goals` - A list of goal strings to test.
  

**Returns**:

  List of dictionaries containing evaluation results,
  or empty list if no goals provided.

