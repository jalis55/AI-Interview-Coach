"""Explicit, bounded attempts for recoverable operations."""

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class AttemptResult[T]:
    value: T | None
    attempts: int
    succeeded: bool


def run_bounded_attempts[T](
    operation: Callable[[], T],
    *,
    max_attempts: int,
    retry_on: tuple[type[Exception], ...],
) -> AttemptResult[T]:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1.")

    for attempt in range(1, max_attempts + 1):
        try:
            value = operation()
        except retry_on:
            continue

        return AttemptResult(
            value=value,
            attempts=attempt,
            succeeded=True,
        )

    return AttemptResult(
        value=None,
        attempts=max_attempts,
        succeeded=False,
    )
