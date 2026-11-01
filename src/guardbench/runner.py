from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from .adapters.base import TargetAdapter
from .metrics import calculate_metrics
from .models import (
    AdapterResult,
    CaseResult,
    Dataset,
    OutcomeStatus,
    RunConfig,
    RunReport,
    RunStatus,
    TestCase,
)


async def _execute_case(
    case: TestCase, adapter: TargetAdapter, config: RunConfig, semaphore: asyncio.Semaphore
) -> CaseResult:
    async with semaphore:
        attempt = 0
        result: AdapterResult
        while True:
            result = await adapter.evaluate(case, config.timeout_seconds)
            retryable = result.error.retryable if result.error else False
            if (
                result.outcome_status == OutcomeStatus.SUCCESS
                or not retryable
                or attempt >= config.retries
            ):
                break
            attempt += 1
        return CaseResult(
            case_id=case.id,
            input=case.input,
            expected_decision=case.expected_decision,
            actual_decision=result.decision,
            outcome_status=result.outcome_status,
            correct=(result.decision == case.expected_decision)
            if result.outcome_status == OutcomeStatus.SUCCESS
            else None,
            reason=result.reason,
            policy_reference=result.policy_reference,
            model=result.model,
            latency_ms=result.latency_ms,
            metadata={**result.metadata, "attempts": attempt + 1},
            error=result.error,
        )


def filter_cases(dataset: Dataset, config: RunConfig) -> list[TestCase]:
    cases = dataset.cases
    if config.categories:
        cases = [case for case in cases if case.category in config.categories]
    if config.tags:
        wanted = set(config.tags)
        cases = [case for case in cases if wanted.intersection(case.tags)]
    return cases


async def run_evaluation(
    dataset: Dataset,
    adapter: TargetAdapter,
    config: RunConfig | None = None,
) -> RunReport:
    config = config or RunConfig()
    started = datetime.now(UTC)
    semaphore = asyncio.Semaphore(config.concurrency)
    cases = filter_cases(dataset, config)
    results = await asyncio.gather(
        *(_execute_case(case, adapter, config, semaphore) for case in cases)
    )
    completed = datetime.now(UTC)
    return RunReport(
        dataset_name=dataset.name,
        dataset_version=dataset.version,
        policy_version=dataset.policy_version,
        target_name=adapter.name,
        target_version=adapter.version,
        status=RunStatus.COMPLETED,
        started_at=started,
        completed_at=completed,
        config=config,
        results=results,
        metrics=calculate_metrics(results),
    )
