"""Job domain models and Pydantic schemas."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class JobStatus(str, Enum):
    """Status of a background job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    """Extensible job type identifier."""

    ENRICHMENT = "enrichment"
    RETRY = "retry"


TERMINAL_STATUSES = frozenset({JobStatus.COMPLETED, JobStatus.ERROR, JobStatus.CANCELLED})


# --- Request / Response schemas ---


class JobCreateRequest(BaseModel):
    """Payload for creating a new job."""

    playlist_id: str
    api_key: Optional[str] = None
    wipe: bool = False
    playlist_name: str = ""


class JobError(BaseModel):
    """A single error entry recorded during a job."""

    track_title: str = ""
    track_video_id: str = ""
    message: str = ""


class AIUsageData(BaseModel):
    """Token / cost counters for AI usage."""

    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0


class JobResponse(BaseModel):
    """Public representation of a job."""

    id: str
    type: str
    playlist_id: str
    playlist_name: str = ""
    owner: str
    status: str
    total: int = 0
    current: int = 0
    message: str = ""
    errors: list[JobError] = []
    ai_usage: AIUsageData = AIUsageData()
    created_at: str = ""
    updated_at: str = ""


class AIUsageResponse(BaseModel):
    """All-time AI usage response."""

    owner: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
