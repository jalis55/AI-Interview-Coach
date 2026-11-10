"""Append bounded activity without prompts, answers, keys, or raw errors."""

from threading import Lock

from ai_interview_coach.models.activity import ActivityEvent
from ai_interview_coach.models.session import InterviewSession

_activity_lock = Lock()

SAFE_FIELDS = {"skill", "query", "result_count", "source", "cache_hit", "attempt", "count"}
SAFE_FIELDS |= {"provider", "http_status", "error_category", "error_code"}


def emit(
    session: InterviewSession,
    event_type: str,
    *,
    status: str = "ok",
    stage: str = "research",
    **metadata,
) -> None:
    safe = {key: value for key, value in metadata.items() if key in SAFE_FIELDS}
    with _activity_lock:
        if event_type == "retry":
            session.usage.retry_attempts += 1
        elif event_type in {"fallback_started", "tool_plan_fallback"}:
            session.usage.fallback_runs += 1
        elif event_type == "safe_default":
            session.usage.safe_defaults += 1
        session.activity_log.append(
            ActivityEvent(
                session_id=session.session_id,
                stage=stage,
                event_type=event_type,
                status=status,
                metadata=safe,
            )
        )
        session.activity_log[:] = session.activity_log[-300:]
