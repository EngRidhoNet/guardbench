from copy import deepcopy

from guardbench.comparison import compare_runs
from guardbench.models import CaseResult, Decision, OutcomeStatus, RunReport


def make_report(actual):
    result = CaseResult(
        case_id="one",
        input="safe",
        expected_decision=Decision.ALLOW,
        actual_decision=actual,
        outcome_status=OutcomeStatus.SUCCESS,
        correct=actual == Decision.ALLOW,
    )
    return RunReport(
        dataset_name="fixture",
        dataset_version="1",
        target_name="target",
        target_version="1",
        results=[result],
        metrics={
            "accuracy": 1 if result.correct else 0,
            "macro_f1": 1 if result.correct else 0,
            "weighted_f1": 1 if result.correct else 0,
            "false_block_rate": 0 if result.correct else 1,
            "missed_block_rate": None,
            "missed_escalation_rate": None,
            "indeterminate_rate": 0,
        },
    )


def test_comparison_identifies_improvement():
    comparison = compare_runs(make_report(Decision.BLOCK), make_report(Decision.ALLOW))
    assert comparison["equivalent"] is True
    assert comparison["cases_improved"] == ["one"]
    assert comparison["metric_deltas"]["accuracy"] == 1


def test_comparison_warns_on_dataset_mismatch():
    candidate = deepcopy(make_report(Decision.ALLOW))
    candidate.dataset_version = "2"
    assert compare_runs(make_report(Decision.ALLOW), candidate)["equivalent"] is False
