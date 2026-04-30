"""Pydantic request/response models for API input validation."""
from pydantic import BaseModel, Field
from typing import Literal, Optional


class CollectRequest(BaseModel):
    title: Optional[str] = None
    max_jobs: int = Field(default=0, ge=0, le=500)


class ApplyRequest(BaseModel):
    mode: Literal["easy", "external", "all"] = "easy"
    limit: Optional[int] = Field(default=None, ge=1, le=500)
    workers: int = Field(default=1, ge=1, le=4)
    job_url: Optional[str] = None


class DecayRequest(BaseModel):
    days: int = Field(default=30, ge=1, le=365)
    factor: float = Field(default=0.95, gt=0, le=1.0)


class CleanupRequest(BaseModel):
    threshold: float = Field(default=0.3, ge=0, le=1.0)
