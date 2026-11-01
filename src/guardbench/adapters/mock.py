from __future__ import annotations

import asyncio
import re
from time import perf_counter

from guardbench.models import AdapterResult, Decision, TestCase

from .base import TargetAdapter


class MockAdapter(TargetAdapter):
    """Deterministic classifier for demos, tests, and credential-free quickstarts."""

    name = "deterministic-mock"
    version = "1"

    def __init__(
        self,
        block_patterns: list[str] | None = None,
        escalate_patterns: list[str] | None = None,
    ) -> None:
        self.block_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in (block_patterns or [r"steal", r"bypass", r"password", r"malware"])
        ]
        self.escalate_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in (
                escalate_patterns or [r"which investment", r"diagnose me", r"legal advice"]
            )
        ]

    async def evaluate(self, case: TestCase, timeout_seconds: float) -> AdapterResult:
        started = perf_counter()
        await asyncio.sleep(0)
        if any(pattern.search(case.input) for pattern in self.block_patterns):
            decision, reason = Decision.BLOCK, "Matched deterministic block rule"
        elif any(pattern.search(case.input) for pattern in self.escalate_patterns):
            decision, reason = Decision.ESCALATE, "Matched deterministic escalation rule"
        else:
            decision, reason = Decision.ALLOW, "No restrictive rule matched"
        return AdapterResult(
            decision=decision,
            reason=reason,
            model="guardbench-mock-v1",
            latency_ms=round((perf_counter() - started) * 1000),
        )
