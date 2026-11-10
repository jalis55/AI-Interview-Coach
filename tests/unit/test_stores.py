"""Tests for isolated session state and conversation history."""

from uuid import uuid4

import pytest

from ai_interview_coach.models.session import InterviewStatus
from ai_interview_coach.stores.history_store import InMemoryHistoryStore
from ai_interview_coach.stores.session_store import (
    InMemorySessionStore,
    SessionNotFoundError,
)


def test_create_registers_unique_sessions():
    store = InMemorySessionStore()

    first = store.create()
    second = store.create()

    assert first.session_id != second.session_id
    assert store.get(first.session_id) is first
    assert store.get(second.session_id) is second
    assert first.status is InterviewStatus.DRAFT


def test_session_changes_are_isolated():
    store = InMemorySessionStore()
    first = store.create()
    second = store.create()

    first.status = InterviewStatus.RECOVERABLE_ERROR

    assert store.get(first.session_id).status is InterviewStatus.RECOVERABLE_ERROR
    assert store.get(second.session_id).status is InterviewStatus.DRAFT


def test_missing_session_raises_clear_error():
    store = InMemorySessionStore()

    with pytest.raises(SessionNotFoundError, match="Interview session not found"):
        store.get(uuid4())


def test_separate_store_instances_do_not_share_sessions():
    first_store = InMemorySessionStore()
    second_store = InMemorySessionStore()
    session = first_store.create()

    with pytest.raises(SessionNotFoundError):
        second_store.get(session.session_id)


def test_history_is_retained_and_isolated():
    store = InMemoryHistoryStore()
    first_id = uuid4()
    second_id = uuid4()

    first_history = store.get(first_id)
    first_history.add_user_message("My answer.")

    assert store.get(first_id) is first_history
    assert first_history.messages[0].content == "My answer."
    assert store.get(second_id).messages == []


def test_clearing_history_preserves_session_state():
    sessions = InMemorySessionStore()
    histories = InMemoryHistoryStore()
    session = sessions.create()

    history = histories.get(session.session_id)
    history.add_user_message("My answer.")
    history.clear()

    assert history.messages == []
    assert sessions.get(session.session_id) is session
