"""Base Pydantic models shared by domain entities."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TimestampedModel(BaseModel):
    """Base model with creation and update timestamps."""

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class IDModel(BaseModel):
    """Base model with a UUID primary identifier."""

    id: UUID = Field(default_factory=uuid4)


class BaseEntity(TimestampedModel, IDModel):
    """Base model for entities that need IDs and timestamps."""

