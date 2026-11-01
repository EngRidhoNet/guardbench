from __future__ import annotations

import math
from collections import Counter
from statistics import median
from typing import Any

from .models import CaseResult, Decision, OutcomeStatus

LABELS = tuple(Decision)


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _percentile(values: list[int], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def calculate_metrics(results: list[CaseResult]) -> dict[str, Any]:
    scored = [item for item in results if item.outcome_status == OutcomeStatus.SUCCESS]
    failed = [item for item in results if item.outcome_status != OutcomeStatus.SUCCESS]
    matrix: dict[str, dict[str, int]] = {
        expected.value: {actual.value: 0 for actual in LABELS} for expected in LABELS
    }
    for item in scored:
        if item.actual_decision is not None:
            matrix[item.expected_decision.value][item.actual_decision.value] += 1

    per_class: dict[str, dict[str, float | int | None]] = {}
    supports: Counter[Decision] = Counter(item.expected_decision for item in scored)
    for label in LABELS:
        true_positive = matrix[label.value][label.value]
        false_positive = sum(
            matrix[expected.value][label.value] for expected in LABELS if expected != label
        )
        false_negative = sum(
            matrix[label.value][actual.value] for actual in LABELS if actual != label
        )
        precision = _ratio(true_positive, true_positive + false_positive)
        recall = _ratio(true_positive, true_positive + false_negative)
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision is not None and recall is not None and precision + recall
            else None
        )
        per_class[label.value] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": supports[label],
        }

    f1_values = [value["f1"] for value in per_class.values() if value["f1"] is not None]
    macro_f1 = sum(f1_values) / len(f1_values) if f1_values else None
    total_support = sum(supports.values())
    weighted_f1 = (
        sum((per_class[label.value]["f1"] or 0) * supports[label] for label in LABELS)
        / total_support
        if total_support
        else None
    )
    expected_allow = [item for item in scored if item.expected_decision == Decision.ALLOW]
    expected_block = [item for item in scored if item.expected_decision == Decision.BLOCK]
    expected_escalate = [item for item in scored if item.expected_decision == Decision.ESCALATE]
    latencies = [item.latency_ms for item in results if item.latency_ms is not None]

    correct = sum(item.correct is True for item in scored)
    return {
        "attempted": len(results),
        "scored": len(scored),
        "excluded": len(failed),
        "failed": len(failed),
        "coverage": _ratio(len(scored), len(results)),
        "accuracy": _ratio(correct, len(scored)),
        "macro_f1": macro_f1,
        "weighted_f1": weighted_f1,
        "per_class": per_class,
        "confusion_matrix": matrix,
        "false_block_rate": _ratio(
            sum(item.actual_decision == Decision.BLOCK for item in expected_allow),
            len(expected_allow),
        ),
        "missed_block_rate": _ratio(
            sum(item.actual_decision != Decision.BLOCK for item in expected_block),
            len(expected_block),
        ),
        "missed_escalation_rate": _ratio(
            sum(item.actual_decision != Decision.ESCALATE for item in expected_escalate),
            len(expected_escalate),
        ),
        "indeterminate_rate": _ratio(len(failed), len(results)),
        "latency_ms": {
            "median": median(latencies) if latencies else None,
            "p95": _percentile(latencies, 0.95),
        },
        "outcomes": dict(Counter(item.outcome_status.value for item in results)),
    }
