"""Safe research activity records; never store provider error payloads."""

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ActivityEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    session_id: UUID
    stage: str
    event_type: str
    status: str
    metadata: dict[str, str | int | bool] = Field(default_factory=dict)
