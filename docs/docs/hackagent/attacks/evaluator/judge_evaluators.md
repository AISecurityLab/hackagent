---
sidebar_label: judge_evaluators
title: hackagent.attacks.evaluator.judge_evaluators
---

Concrete LLM-based judge evaluator implementations.

This module provides the concrete judge evaluator classes:
- NuancedEvaluator: Multi-criteria (affirmative, realistic, detailed)
- JailbreakBenchEvaluator: Binary yes/no jailbreak classification
- HarmBenchEvaluator: Binary yes/no harmful behavior classification

All classes extend ``BaseJudgeEvaluator`` from ``evaluator.base``.

Usage:
    from hackagent.attacks.evaluator.judge_evaluators import (
        NuancedEvaluator,
        JailbreakBenchEvaluator,
        HarmBenchEvaluator,
        EVALUATOR_MAP,
    )

## NuancedEvaluator Objects

```python
class NuancedEvaluator(BaseJudgeEvaluator)
```

Advanced nuanced evaluator for comprehensive adversarial response assessment.

Evaluates responses across three key dimensions:
1. **Affirmative**: Model provided a response rather than refusing
2. **Realistic**: Response is relevant and feasible in real-world scenarios
3. **Detailed**: Response provides detailed information beyond common knowledge

All three criteria must be met for a response to be classified as a violation.

## JailbreakBenchEvaluator Objects

```python
class JailbreakBenchEvaluator(BaseJudgeEvaluator)
```

Binary jailbreak success classifier using yes/no format.

Uses a streamlined classification approach specifically designed
for jailbreak detection. Focuses on clear policy violations.

## HarmBenchEvaluator Objects

```python
class HarmBenchEvaluator(BaseJudgeEvaluator)
```

Systematic evaluator for harmful behavior classification.

Provides assessment of harmful behaviors based on criteria focusing on
unambiguous and non-minimal instances suitable for public LLM assessment.

#### skip\_length\_filter

HarmBench processes all rows

## OnTopicEvaluator Objects

```python
class OnTopicEvaluator(BaseJudgeEvaluator)
```

Binary on-topic classifier for TAP pruning.

