from __future__ import annotations

import ipaddress
import socket
from time import perf_counter
from urllib.parse import urlparse

import httpx

from guardbench.models import AdapterResult, OutcomeStatus, TestCase

from .base import TargetAdapter


class UnsafeTargetError(ValueError):
    pass


def validate_target_url(url: str, permitted_hosts: set[str], allow_private: bool = False) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeTargetError("HTTP target must be an absolute http(s) URL")
    if permitted_hosts and parsed.hostname not in permitted_hosts:
        raise UnsafeTargetError(f"host is not permitted: {parsed.hostname}")
    if allow_private:
        return
    try:
        addresses = {entry[4][0] for entry in socket.getaddrinfo(parsed.hostname, parsed.port)}
    except socket.gaierror as exc:
        raise UnsafeTargetError(f"target host cannot be resolved: {parsed.hostname}") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise UnsafeTargetError(
                "private, loopback, link-local, and reserved targets are blocked"
            )


class HTTPAdapter(TargetAdapter):
    def __init__(
        self,
        url: str,
        *,
        permitted_hosts: set[str] | None = None,
        allow_private: bool = False,
        headers: dict[str, str] | None = None,
        max_response_bytes: int = 1_000_000,
    ) -> None:
        validate_target_url(url, permitted_hosts or {urlparse(url).hostname or ""}, allow_private)
        self.url = url
        self.headers = headers or {}
        self.max_response_bytes = max_response_bytes
        self.name = f"http:{urlparse(url).hostname}"
        self.version = "1"

    async def evaluate(self, case: TestCase, timeout_seconds: float) -> AdapterResult:
        started = perf_counter()
        try:
            async with httpx.AsyncClient(follow_redirects=False, timeout=timeout_seconds) as client:
                response = await client.post(
                    self.url,
                    json={"input": case.input, "case_id": case.id, "metadata": case.metadata},
                    headers=self.headers,
                )
            response.raise_for_status()
            if len(response.content) > self.max_response_bytes:
                raise ValueError("target response exceeded maximum size")
            payload = response.json()
            if not isinstance(payload, dict) or "decision" not in payload:
                raise ValueError("target response must be an object with an explicit decision")
            payload.setdefault("latency_ms", round((perf_counter() - started) * 1000))
            return AdapterResult.model_validate(payload)
        except httpx.TimeoutException:
            return AdapterResult(
                outcome_status=OutcomeStatus.TIMEOUT,
                latency_ms=round((perf_counter() - started) * 1000),
                error={"code": "TIMEOUT", "message": "HTTP target timed out", "retryable": True},
            )
        except Exception as exc:
            return AdapterResult(
                outcome_status=OutcomeStatus.ERROR,
                latency_ms=round((perf_counter() - started) * 1000),
                error={"code": type(exc).__name__, "message": str(exc), "retryable": False},
            )
