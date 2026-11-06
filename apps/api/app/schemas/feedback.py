from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    rating: Literal["helpful", "unhelpful"]
    reason: Literal["inaccurate", "no_citation", "outdated", "missing_steps", "other"] | None = None
    comment: str = Field(default="", max_length=1000)


class FeedbackOut(BaseModel):
    id: str
    message_id: str
    user_id: str
    rating: str
    reason: str | None = None
    comment: str
    created_at: datetime
    updated_at: datetime
