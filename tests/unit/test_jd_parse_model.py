"""Validation tests for JD parsing outcomes."""

import pytest
from pydantic import ValidationError

from ai_interview_coach.models.jd_parse import JDParseResult


@pytest.fixture
def requirements():
    return {
        "role": "Backend Engineer",
        "seniority": "mid",
        "core_skills": ["python", "sql"],
        "nice_to_have": [],
    }


def test_valid_result_contains_requirements(requirements):
    result = JDParseResult(
        status="valid",
        requirements=requirements,
        message="Please review the extracted requirements.",
    )

    assert result.requirements is not None
    assert result.requirements.core_skills == ["python", "sql"]


def test_correction_result_has_no_requirements():
    result = JDParseResult(
        status="needs_correction",
        requirements=None,
        message="Please provide a role and required skills.",
    )

    assert result.requirements is None


def test_valid_result_rejects_missing_requirements():
    with pytest.raises(ValidationError):
        JDParseResult(
            status="valid",
            requirements=None,
            message="Requirements extracted.",
        )


def test_correction_result_rejects_requirements(requirements):
    with pytest.raises(ValidationError):
        JDParseResult(
            status="needs_correction",
            requirements=requirements,
            message="Please clarify the role.",
        )


@pytest.mark.parametrize("message", ["", "   "])
def test_result_rejects_blank_message(message):
    with pytest.raises(ValidationError):
        JDParseResult(
            status="needs_correction",
            requirements=None,
            message=message,
        )


def test_result_rejects_unknown_status():
    with pytest.raises(ValidationError):
        JDParseResult(
            status="success",
            requirements=None,
            message="Example message.",
        )
