from guardbench.metrics import calculate_metrics
from guardbench.models import CaseResult, Decision, OutcomeStatus


def result(case_id, expected, actual=None, outcome=OutcomeStatus.SUCCESS):
    return CaseResult(
        case_id=case_id,
        input="test",
        expected_decision=expected,
        actual_decision=actual,
        outcome_status=outcome,
        correct=actual == expected if actual else None,
    )


def test_metrics_distinguish_errors_and_decisions():
    metrics = calculate_metrics(
        [
            result("1", Decision.ALLOW, Decision.ALLOW),
            result("2", Decision.ALLOW, Decision.BLOCK),
            result("3", Decision.BLOCK, Decision.BLOCK),
            result("4", Decision.ESCALATE, outcome=OutcomeStatus.TIMEOUT),
        ]
    )
    assert metrics["attempted"] == 4
    assert metrics["scored"] == 3
    assert metrics["coverage"] == 0.75
    assert metrics["accuracy"] == 2 / 3
    assert metrics["false_block_rate"] == 0.5
    assert metrics["missed_block_rate"] == 0
    assert metrics["missed_escalation_rate"] is None
    assert metrics["indeterminate_rate"] == 0.25


def test_zero_denominators_are_unavailable():
    metrics = calculate_metrics([result("1", Decision.ALLOW, Decision.ALLOW)])
    assert metrics["missed_block_rate"] is None
    assert metrics["missed_escalation_rate"] is None
