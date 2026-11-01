from __future__ import annotations

import asyncio
import importlib
import inspect
from collections.abc import Callable
from time import perf_counter
from typing import Any

from guardbench.models import AdapterResult, OutcomeStatus, TestCase

from .base import TargetAdapter


class PythonCallableAdapter(TargetAdapter):
    def __init__(self, callable_path: str) -> None:
        module_name, separator, attribute = callable_path.partition(":")
        if not separator:
            raise ValueError("callable must use module.path:function syntax")
        callback = getattr(importlib.import_module(module_name), attribute)
        if not callable(callback):
            raise TypeError(f"{callable_path} is not callable")
        self.callback: Callable[..., Any] = callback
        self.name = callable_path
        self.version = "1"

    async def evaluate(self, case: TestCase, timeout_seconds: float) -> AdapterResult:
        started = perf_counter()
        try:
            if inspect.iscoroutinefunction(self.callback):
                raw = await asyncio.wait_for(self.callback(case.input), timeout_seconds)
            else:
                raw = await asyncio.wait_for(
                    asyncio.to_thread(self.callback, case.input), timeout_seconds
                )
            payload = raw if isinstance(raw, dict) else {"decision": raw}
            payload.setdefault("latency_ms", round((perf_counter() - started) * 1000))
            return AdapterResult.model_validate(payload)
        except TimeoutError:
            return AdapterResult(
                outcome_status=OutcomeStatus.TIMEOUT,
                latency_ms=round((perf_counter() - started) * 1000),
                error={"code": "TIMEOUT", "message": "Python target timed out", "retryable": True},
            )
        except Exception as exc:  # target exceptions are data, not runner failures
            return AdapterResult(
                outcome_status=OutcomeStatus.ERROR,
                latency_ms=round((perf_counter() - started) * 1000),
                error={"code": type(exc).__name__, "message": str(exc), "retryable": False},
            )
