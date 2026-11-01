from __future__ import annotations

from abc import ABC, abstractmethod

from guardbench.models import AdapterResult, TestCase


class TargetAdapter(ABC):
    name: str
    version: str

    @abstractmethod
    async def evaluate(self, case: TestCase, timeout_seconds: float) -> AdapterResult:
        """Evaluate one case and return a canonical result."""
