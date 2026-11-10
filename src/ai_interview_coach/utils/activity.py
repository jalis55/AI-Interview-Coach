"""Append bounded activity without prompts, answers, keys, or raw errors."""

from ai_interview_coach.models.activity import ActivityEvent
from ai_interview_coach.models.session import InterviewSession

SAFE_FIELDS = {"skill", "query", "result_count", "source", "cache_hit", "attempt", "count"}
SAFE_FIELDS |= {"provider", "http_status", "error_category", "error_code"}


def emit(session: InterviewSession, event_type: str, *, status: str = "ok", **metadata) -> None:
    safe = {key: value for key, value in metadata.items() if key in SAFE_FIELDS}
    session.activity_log.append(
        ActivityEvent(
            session_id=session.session_id,
            stage="research",
            event_type=event_type,
            status=status,
            metadata=safe,
        )
    )
    session.activity_log[:] = session.activity_log[-300:]
