from __future__ import annotations

from typing import Any

from .models import RunReport

METRIC_PATHS = (
    "accuracy",
    "macro_f1",
    "weighted_f1",
    "false_block_rate",
    "missed_block_rate",
    "missed_escalation_rate",
    "indeterminate_rate",
)


def compare_runs(baseline: RunReport, candidate: RunReport) -> dict[str, Any]:
    warnings: list[str] = []
    for field in ("dataset_name", "dataset_version", "policy_version"):
        if getattr(baseline, field) != getattr(candidate, field):
            warnings.append(f"{field} differs")
    deltas = {}
    for metric in METRIC_PATHS:
        before = baseline.metrics.get(metric)
        after = candidate.metrics.get(metric)
        deltas[metric] = after - before if before is not None and after is not None else None

    base_by_case = {item.case_id: item for item in baseline.results}
    candidate_by_case = {item.case_id: item for item in candidate.results}
    improved, regressed, changed = [], [], []
    for case_id in sorted(base_by_case.keys() & candidate_by_case.keys()):
        before = base_by_case[case_id]
        after = candidate_by_case[case_id]
        if (
            before.actual_decision != after.actual_decision
            or before.outcome_status != after.outcome_status
        ):
            changed.append(case_id)
        if before.correct is not True and after.correct is True:
            improved.append(case_id)
        elif before.correct is True and after.correct is not True:
            regressed.append(case_id)
    return {
        "equivalent": not warnings,
        "warnings": warnings,
        "metric_deltas": deltas,
        "cases_improved": improved,
        "cases_regressed": regressed,
        "cases_changed": changed,
    }
