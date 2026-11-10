"""LCEL thresholds, clamping, and defaulted-evaluation routing."""

import pytest

from ai_interview_coach.chains.adaptation import build_difficulty_router
from ai_interview_coach.models.plan import Difficulty


@pytest.mark.parametrize(
    ("current", "score", "status", "expected"),
    [
        ("medium", 3, "valid", "easy"),
        ("medium", 4, "valid", "medium"),
        ("medium", 8, "valid", "medium"),
        ("medium", 9, "valid", "hard"),
        ("easy", 1, "valid", "easy"),
        ("hard", 10, "valid", "hard"),
        ("medium", 3, "defaulted", "medium"),
        ("easy", 9, "defaulted", "easy"),
    ],
)
def test_difficulty_thresholds(current, score, status, expected):
    routed = build_difficulty_router().invoke(
        {
            "current": current,
            "score": score,
            "status": status,
        }
    )
    assert routed is Difficulty(expected)
