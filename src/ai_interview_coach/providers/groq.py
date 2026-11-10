"""Groq chat-model configuration."""

from langchain_groq import ChatGroq

from ai_interview_coach.config import get_settings


def create_chat_model() -> ChatGroq:
    settings = get_settings()

    return ChatGroq(
        model=settings.groq_model,
        api_key=settings.groq_api_key,
        temperature=0,
        timeout=settings.request_timeout_seconds,
        max_retries=0,
        max_tokens=settings.max_output_tokens,
    )
