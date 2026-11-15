"""Pydantic request/response models for API input validation."""
from pydantic import BaseModel, Field
from typing import Literal, Optional


class CollectRequest(BaseModel):
    title: Optional[str] = None
    max_jobs: int = Field(default=0, ge=0, le=500)
    source: str = Field(default="linkedin", description="Plugin name to collect from")
    filters: dict = Field(default_factory=dict, description="Plugin-specific filter key-value pairs")


class ApplyRequest(BaseModel):
    mode: Literal["easy", "external", "all"] = "easy"
    limit: Optional[int] = Field(default=None, ge=1, le=500)
    workers: int = Field(default=1, ge=1, le=4)
    job_url: Optional[str] = None
    job_urls: Optional[list[str]] = Field(default=None, description="Specific job URLs to apply to (batch apply)")
    test_mode: bool = Field(default=False, description="Click Submit but intercept the request (nothing is sent)")


class CollectFilters(BaseModel):
    filters: dict = Field(default_factory=dict, description="Plugin-specific filter key-value pairs")


class DecayRequest(BaseModel):
    days: int = Field(default=30, ge=1, le=365)
    factor: float = Field(default=0.95, gt=0, le=1.0)


class CleanupRequest(BaseModel):
    threshold: float = Field(default=0.3, ge=0, le=1.0)


class PluginImportRequest(BaseModel):
    file_path: str = Field(description="Path to the .yaml plugin file to import")
    approved_sha256: Optional[str] = Field(default=None, description="Hash the user reviewed (from /plugins/preview)")


class PluginToggleRequest(BaseModel):
    enabled: bool = Field(description="Whether the plugin should be enabled")


# ── Typed request bodies (previously bare `dict`) ───────────────────────────
from typing import Any  # noqa: E402

from pydantic import ConfigDict  # noqa: E402

JobStatus = Literal["pending", "applied", "failed", "blocked", "skipped", "needs_input"]


class _Open(BaseModel):
    """Known fields are validated; unknown ones are kept (forward compatible)."""
    model_config = ConfigDict(extra="allow")


class Address(_Open):
    street: str = ""
    city: str = ""
    state: str = ""
    zip: str = ""
    country: str = ""


class Education(_Open):
    degree: str = ""
    school: str = ""
    graduation: str = ""


class Salary(_Open):
    min: float = 0
    max: float = 0
    currency: str = "USD"
    period: str = "annual"


class ProfileBody(_Open):
    name: str = ""
    email: str = ""
    phone: str = ""
    phone_country_code: str = ""
    country: str = ""
    address: Address = Field(default_factory=Address)
    education: Education = Field(default_factory=Education)
    salary_expectation: Salary = Field(default_factory=Salary)
    years_of_experience: float = 0
    target_job_titles: list[str] = Field(default_factory=list)
    target_locations: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    visa_sponsorship_needed: bool = False
    willing_to_relocate: bool = False


class SensitiveData(_Open):
    email: str = ""
    password: str = ""


class SettingsBody(_Open):
    resume_path: str = ""
    blocked_domains: list[str] = Field(default_factory=list)
    sensitive_data: SensitiveData = Field(default_factory=SensitiveData)
    # Out-of-range numbers are clamped by save_settings rather than rejected
    max_failures: int = 8
    stagger_delay: int = 5
    telemetry_enabled: bool = False
    log_retention_days: int = 14
    daily_apply_cap: int = 25
    max_run_cost_usd: float = 5.0
    browser_cdp_url: str = ""
    email_otp_via_gmail: bool = False
    test_mode: bool = False


class LLMSettingsBody(_Open):
    provider: str = Field(default="", max_length=64)


class OllamaModelsRequest(BaseModel):
    base_url: str = "http://localhost:11434"


class JobStatusUpdate(BaseModel):
    url: str = Field(min_length=1)
    status: JobStatus


class JobAddRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)
    title: str = ""
    company: str = ""
    location: str = ""
    source: str = "manual"
    description: str = ""


class JobsDeleteRequest(BaseModel):
    urls: list[str] = Field(min_length=1)


class QAUpdateRequest(BaseModel):
    answer: str = ""


class TailorOptions(_Open):
    skills: bool = True
    overview: bool = True
    experience: bool = True
    title: bool = False


class TailorRequest(BaseModel):
    job_urls: list[str] = Field(min_length=1)
    options: TailorOptions = Field(default_factory=TailorOptions)


class RefineRequest(BaseModel):
    job_url: str = Field(min_length=1)
    instruction: str = ""
    options: TailorOptions = Field(default_factory=TailorOptions)


class JobUrlRequest(BaseModel):
    job_url: str = Field(min_length=1)


class CoverLetterRequest(BaseModel):
    job_description: str = Field(min_length=1)
    job_title: str = ""
    company: str = ""


class DataDeleteRequest(BaseModel):
    confirm: Literal[True]


class PluginPreviewRequest(BaseModel):
    file_path: str


class MemoryPackImport(BaseModel):
    pack: dict[str, Any]
