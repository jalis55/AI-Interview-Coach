"""Token accounting uses actual callback metadata, never assumed prices."""

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from ai_interview_coach.models.session import InterviewSession
from ai_interview_coach.utils.usage import UsageCollector, model_config


def test_chat_callbacks_count_requests_and_reported_tokens_once():
    session = InterviewSession()
    model = FakeMessagesListChatModel(
        responses=[
            AIMessage(
                content="Result",
                usage_metadata={"input_tokens": 11, "output_tokens": 7, "total_tokens": 18},
            )
        ]
    )
    model.invoke("Private prompt", config=model_config(session, "evaluation"))
    assert session.usage.provider_calls == 1
    assert session.usage.metered_responses == 1
    assert session.usage.input_tokens == 11
    assert session.usage.output_tokens == 7
    assert session.usage.calls_by_stage == {"evaluation": 1}
    assert "Private prompt" not in session.usage.model_dump_json()


def test_failures_are_counted_without_error_payloads():
    session = InterviewSession()
    collector = UsageCollector(session, "generation")
    collector.on_chat_model_start({}, [])
    collector.on_llm_error(RuntimeError("PRIVATE_ERROR"))
    assert session.usage.failed_calls == 1
    assert session.usage.provider_calls == 1
    assert "PRIVATE_ERROR" not in session.usage.model_dump_json()


def test_usage_is_separate_between_sessions():
    first, second = InterviewSession(), InterviewSession()
    UsageCollector(first, "report").on_chat_model_start({}, [])
    assert first.usage.provider_calls == 1
    assert second.usage.provider_calls == 0


def test_retry_and_fallback_totals_survive_activity_log_trimming():
    from ai_interview_coach.utils.activity import emit

    session = InterviewSession()
    emit(session, "retry", stage="evaluation")
    emit(session, "fallback_started", stage="evaluation")
    emit(session, "safe_default", stage="evaluation")
    for _ in range(305):
        emit(session, "ordinary_event")
    assert len(session.activity_log) == 300
    assert session.usage.retry_attempts == 1
    assert session.usage.fallback_runs == 1
    assert session.usage.safe_defaults == 1
