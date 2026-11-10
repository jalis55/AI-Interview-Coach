"""Tests for bounded attempts without provider calls."""

import pytest

from ai_interview_coach.utils.reliability import run_bounded_attempts


def test_returns_after_first_success():
    calls = []

    def operation():
        calls.append(1)
        return "needs_correction"

    result = run_bounded_attempts(
        operation,
        max_attempts=3,
        retry_on=(ValueError,),
    )

    assert result.succeeded
    assert result.value == "needs_correction"
    assert result.attempts == 1
    assert len(calls) == 1


def test_retries_then_returns_success():
    calls = []

    def operation():
        calls.append(1)
        if len(calls) < 3:
            raise ValueError("Malformed output.")
        return "valid"

    result = run_bounded_attempts(
        operation,
        max_attempts=3,
        retry_on=(ValueError,),
    )

    assert result.succeeded
    assert result.value == "valid"
    assert result.attempts == 3
    assert len(calls) == 3


def test_stops_at_attempt_limit():
    calls = []

    def operation():
        calls.append(1)
        raise ValueError("Malformed output.")

    result = run_bounded_attempts(
        operation,
        max_attempts=3,
        retry_on=(ValueError,),
    )

    assert not result.succeeded
    assert result.value is None
    assert result.attempts == 3
    assert len(calls) == 3


def test_unexpected_errors_propagate():
    def operation():
        raise RuntimeError("Unexpected failure.")

    with pytest.raises(RuntimeError, match="Unexpected failure"):
        run_bounded_attempts(
            operation,
            max_attempts=3,
            retry_on=(ValueError,),
        )


def test_rejects_invalid_attempt_limit():
    with pytest.raises(ValueError, match="at least 1"):
        run_bounded_attempts(
            lambda: "unused",
            max_attempts=0,
            retry_on=(ValueError,),
        )
