"""Configuration tests that never read the real .env file."""

import pytest
from pydantic import ValidationError

from ai_interview_coach.config import Settings


@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch):
    """Remove application settings inherited from the environment."""
    names = [
        "GROQ_API_KEY",
        "TAVILY_API_KEY",
        "GROQ_MODEL",
        "REQUEST_TIMEOUT_SECONDS",
        "PRIMARY_MAX_ATTEMPTS",
        "FALLBACK_MAX_ATTEMPTS",
    ]

    for name in names:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def valid_settings():
    return {
        "groq_api_key": "test-groq-key",
        "tavily_api_key": "test-tavily-key",
        "groq_model": "test-model",
    }


def test_settings_loads_environment_variables(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("TAVILY_API_KEY", "test-tavily-key")
    monkeypatch.setenv("GROQ_MODEL", "test-model")

    settings = Settings(_env_file=None)

    assert settings.groq_api_key.get_secret_value() == "test-groq-key"
    assert settings.tavily_api_key.get_secret_value() == "test-tavily-key"
    assert settings.groq_model == "test-model"
    assert settings.request_timeout_seconds == 30.0


@pytest.mark.parametrize(
    "field",
    ["groq_api_key", "tavily_api_key", "groq_model"],
)
def test_settings_rejects_missing_required_values(valid_settings, field):
    valid_settings.pop(field)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, **valid_settings)


@pytest.mark.parametrize(
    "field",
    ["groq_api_key", "tavily_api_key", "groq_model"],
)
@pytest.mark.parametrize("value", ["", "   "])
def test_settings_rejects_blank_required_values(valid_settings, field, value):
    valid_settings[field] = value

    with pytest.raises(ValidationError):
        Settings(_env_file=None, **valid_settings)


@pytest.mark.parametrize("timeout", [0, -1, 121])
def test_settings_rejects_invalid_timeout(valid_settings, timeout):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            request_timeout_seconds=timeout,
            **valid_settings,
        )


def test_settings_masks_keys_in_representation(valid_settings):
    settings = Settings(_env_file=None, **valid_settings)

    representation = repr(settings)

    assert "test-groq-key" not in representation
    assert "test-tavily-key" not in representation
