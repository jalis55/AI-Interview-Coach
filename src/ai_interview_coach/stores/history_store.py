"""In-memory conversation history, separate from interview state."""

from uuid import UUID

from langchain_core.chat_history import InMemoryChatMessageHistory


class InMemoryHistoryStore:
    def __init__(self) -> None:
        self._histories: dict[UUID, InMemoryChatMessageHistory] = {}

    def get(self, session_id: UUID) -> InMemoryChatMessageHistory:
        if session_id not in self._histories:
            self._histories[session_id] = InMemoryChatMessageHistory()

        return self._histories[session_id]
