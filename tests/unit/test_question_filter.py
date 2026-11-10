"""Question provenance, quality, and exclusion checks."""

import pytest
from pydantic import ValidationError

from ai_interview_coach.models.question import InterviewQuestion, QuestionBatch
from ai_interview_coach.models.research import SearchOutcome
from ai_interview_coach.tools.question_filter import filter_questions

TEXT = "How would you investigate a slow SQL query?"
URL = "https://example.com/sql"


def question(**changes):
    data = dict(
        question=TEXT,
        skill="sql",
        difficulty="medium",
        source="web",
        source_url=URL,
        source_title="Untrusted title",
        rationale="SQL diagnosis.",
    )
    return InterviewQuestion(**(data | changes))


def filter_batch(questions, *, exclusions=None, web=True):
    return filter_questions(
        QuestionBatch(questions=questions),
        skill="sql",
        research=SearchOutcome(
            status="success",
            snippets=[
                {
                    "url": URL,
                    "title": "Evidence title",
                    "content": TEXT,
                }
            ],
        ),
        exclusions=exclusions or [],
        web=web,
        limit=6,
    )


def test_supported_web_question_retains_evidence_title():
    accepted = filter_batch([question()])
    assert len(accepted) == 1
    assert accepted[0].source == "web"
    assert accepted[0].source_title == "Evidence title"


@pytest.mark.parametrize(
    "changes",
    [
        {"question": "What is the capital of France?"},
        {"question": "This SQL answer discusses query execution."},
        {"question": "How would you optimize a slow SQL query?"},
        {"skill": "python"},
        {"source_url": "https://invented.com/sql"},
    ],
)
def test_unsupported_or_irrelevant_candidates_are_rejected(changes):
    assert filter_batch([question(**changes)]) == []


def test_asked_and_duplicate_questions_are_excluded():
    assert filter_batch([question()], exclusions=[TEXT]) == []
    assert len(filter_batch([question(), question()])) == 1


def test_newly_generated_questions_cannot_claim_web_provenance():
    accepted = filter_batch([question()], web=False)
    assert accepted[0].source == "llm_fallback"
    assert accepted[0].source_url is None
    assert accepted[0].source_title is None


def test_web_question_requires_url():
    with pytest.raises(ValidationError):
        question(source_url=None)


def test_empty_batch_is_valid():
    assert QuestionBatch(questions=[]).questions == []
