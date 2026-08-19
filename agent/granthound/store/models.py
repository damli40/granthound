from enum import Enum

from pydantic import BaseModel, Field


class Disposition(str, Enum):
    # discovery
    ADDED = "added"
    SOURCE_ADDED = "source_added"
    NO_PROGRAM_FOUND = "no_program_found"
    # liveness - positive
    VERIFIED_LIVE = "verified_live"
    REVERIFIED_LIVE = "reverified_live"
    # liveness - negative
    VERIFIED_DEAD_CLOSED = "verified_dead_closed"
    VERIFIED_DEAD_FINAL_CALL = "verified_dead_final_call"
    VERIFIED_DEAD_PRIOR_YEAR = "verified_dead_prior_year"
    PAGE_UNREACHABLE = "page_unreachable"
    # suspicion (deterministic flags the LLM could not clear)
    STALE_DATE_SUSPECT = "stale_date_suspect"
    YEAR_TRAP_SUSPECT = "year_trap_suspect"
    DATE_CONTRADICTION = "date_contradiction"
    # change detection
    CHANGED_DEADLINE = "changed_deadline"
    CHANGED_TERMS = "changed_terms"
    CHANGED_NEW_ROUND = "changed_new_round"
    # fit outcomes
    SKIPPED_ELIGIBILITY = "skipped_eligibility"
    SKIPPED_FIT_LOW_SCORE = "skipped_fit_low_score"
    SKIPPED_EFFORT_VS_AWARD = "skipped_effort_vs_award"
    PASSED_TERMS = "passed_terms"
    # lifecycle
    WATCH_COMING_SOON = "watch_coming_soon"


class Verdict(str, Enum):
    APPLY = "APPLY"
    PASS = "PASS"
    WATCH = "WATCH"
    NEEDS_HUMAN = "NEEDS_HUMAN"


class FoundDate(BaseModel):
    raw: str
    iso: str | None
    year_present: bool
    context: str


class DateScan(BaseModel):
    dates: list[FoundDate]
    all_dates_past: bool
    has_yearless_date: bool
    dates_contradict: bool


class SnapshotReceipt(BaseModel):
    sha256: str
    s3_raw: str
    s3_norm: str
    fetched_at: str
    http_status: int


class DiffResult(BaseModel):
    changed: bool
    date_lines_changed: bool
    added_lines: int
    removed_lines: int
    diff_text: str


class FitAxes(BaseModel):
    eligibility: float = Field(ge=0, le=5)
    explicit_funding: float = Field(ge=0, le=5)
    effort_to_award: float = Field(ge=0, le=5)
    strategic: float = Field(ge=0, le=5)
    reliability: float = Field(ge=0, le=5)


class FitScore(BaseModel):
    score: float
    capped: bool
    verdict_suggestion: Verdict
