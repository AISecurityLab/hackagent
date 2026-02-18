# Copyright 2026 - AI4I. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Metrics and evaluation analysis utilities.

This module provides reusable metric calculation and analysis
functions for attack evaluation.

Functions:
    calculate_success_rate: Overall success rate from results
    calculate_confidence_score: Average confidence from results
    group_by_goal: Group results by goal
    calculate_per_goal_metrics: Per-goal metric breakdown
    generate_summary_report: Comprehensive summary report

Usage:
    from hackagent.attacks.evaluator.metrics import (
        calculate_success_rate,
        generate_summary_report,
    )
"""

from typing import Any, Dict, List


def calculate_success_rate(results: List[Dict[str, Any]]) -> float:
    """
    Calculate overall success rate from results.

    Args:
        results: List of attack result dictionaries

    Returns:
        Success rate as float between 0 and 1
    """
    if not results:
        return 0.0

    successful = sum(1 for r in results if r.get("success", False))
    return successful / len(results)


def calculate_confidence_score(results: List[Dict[str, Any]]) -> float:
    """
    Calculate average confidence score from results.

    Args:
        results: List of attack result dictionaries

    Returns:
        Average confidence score
    """
    if not results:
        return 0.0

    scores = [r.get("confidence", 0.0) for r in results]
    return sum(scores) / len(scores)


def group_by_goal(results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group results by goal.

    Args:
        results: List of attack result dictionaries

    Returns:
        Dictionary mapping goals to their results
    """
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for result in results:
        goal = result.get("goal", "unknown")
        if goal not in grouped:
            grouped[goal] = []
        grouped[goal].append(result)
    return grouped


def calculate_per_goal_metrics(
    results: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """
    Calculate metrics for each goal separately.

    Args:
        results: List of attack result dictionaries

    Returns:
        Dictionary mapping goals to their metrics
    """
    grouped = group_by_goal(results)

    metrics: Dict[str, Dict[str, Any]] = {}
    for goal, goal_results in grouped.items():
        metrics[goal] = {
            "total_attempts": len(goal_results),
            "successful_attacks": sum(
                1 for r in goal_results if r.get("success", False)
            ),
            "success_rate": calculate_success_rate(goal_results),
            "avg_confidence": calculate_confidence_score(goal_results),
        }

    return metrics


def generate_summary_report(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate comprehensive summary report from results.

    Args:
        results: List of attack result dictionaries

    Returns:
        Summary report dictionary
    """
    return {
        "total_attacks": len(results),
        "overall_success_rate": calculate_success_rate(results),
        "overall_confidence": calculate_confidence_score(results),
        "per_goal_metrics": calculate_per_goal_metrics(results),
        "unique_goals": len(group_by_goal(results)),
    }
