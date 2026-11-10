"""In-memory storage for interview sessions."""

from threading import RLock
from uuid import UUID

from ai_interview_coach.models.session import InterviewSession


class SessionNotFoundError(LookupError):
    """Raised when the requested interview session does not exist."""


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[UUID, InterviewSession] = {}
        self._locks = {}

    def lock(self, session_id: UUID):
        return self._locks.setdefault(session_id, RLock())

    def create(self) -> InterviewSession:
        session = InterviewSession()
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: UUID) -> InterviewSession:
        try:
            return self._sessions[session_id]
        except KeyError:
            raise SessionNotFoundError(
                "Interview session not found. Please start a new interview."
            ) from None
