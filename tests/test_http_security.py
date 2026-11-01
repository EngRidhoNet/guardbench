import pytest

from guardbench.adapters.http import UnsafeTargetError, validate_target_url


def test_rejects_non_http_protocols():
    with pytest.raises(UnsafeTargetError):
        validate_target_url("file:///etc/passwd", set())


def test_rejects_host_outside_allowlist():
    with pytest.raises(UnsafeTargetError, match="not permitted"):
        validate_target_url("https://example.com/evaluate", {"allowed.example"})


def test_allows_explicit_local_development_target():
    validate_target_url("http://localhost:8080/evaluate", {"localhost"}, allow_private=True)
