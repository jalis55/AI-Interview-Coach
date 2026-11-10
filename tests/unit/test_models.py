"""Tests for job requirements and answer-score contracts."""

import pytest
from pydantic import ValidationError

from ai_interview_coach.models.evaluation import AnswerScore
from ai_interview_coach.models.job import JobRequirements, Seniority


def test_job_requirements_normalizes_and_deduplicates_skills():
    requirements = JobRequirements(
        role=" Backend Engineer ",
        seniority="mid",
        core_skills=[" Python ", "SQL", "python", "Machine   Learning"],
    )

    assert requirements.role == "Backend Engineer"
    assert requirements.seniority is Seniority.MID
    assert requirements.core_skills == ["python", "sql", "machine learning"]
    assert requirements.nice_to_have == []


@pytest.mark.parametrize("skills", [[], [""], ["   "]])
def test_job_requirements_rejects_empty_or_blank_core_skills(skills):
    with pytest.raises(ValidationError):
        JobRequirements(
            role="Backend Engineer",
            seniority="mid",
            core_skills=skills,
        )


@pytest.mark.parametrize("role", ["", "   "])
def test_job_requirements_rejects_blank_role(role):
    with pytest.raises(ValidationError):
        JobRequirements(
            role=role,
            seniority="mid",
            core_skills=["python"],
        )


@pytest.mark.parametrize("score", [1, 5, 10])
def test_answer_score_accepts_valid_integers(score):
    result = AnswerScore(
        score=score,
        feedback="Correct explanation.",
        strengths=["Explains the main concept."],
        improvements=[],
    )

    assert result.score == score


@pytest.mark.parametrize("score", [0, 11, 8.5, 8.0, "8", True, False])
def test_answer_score_rejects_invalid_values(score):
    with pytest.raises(ValidationError):
        AnswerScore(
            score=score,
            feedback="Example feedback.",
            strengths=[],
            improvements=[],
        )


@pytest.mark.parametrize("feedback", ["", "   "])
def test_answer_score_rejects_blank_feedback(feedback):
    with pytest.raises(ValidationError):
        AnswerScore(
            score=5,
            feedback=feedback,
            strengths=[],
            improvements=[],
        )
