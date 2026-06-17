"""Shared domain models for yoktez-mcp.

These dataclasses and enums are the shared vocabulary imported by every
other module: search, detail, index, server.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# ---------------------------------------------------------------------------
# Tur enum code ↔ label mappings (verified live, Faz 0)
# ---------------------------------------------------------------------------

THESIS_TYPE_BY_CODE: dict[str, str] = {
    "1": "Yüksek Lisans",
    "2": "Doktora",
    "3": "Tıpta Uzmanlık",
    "4": "Sanatta Yeterlik",
    "5": "Diş Hekimliği Uzmanlık",
    "6": "Tıpta Yan Dal Uzmanlık",
    "7": "Eczacılıkta Uzmanlık",
}

THESIS_TYPE_TO_CODE: dict[str, str] = {v: k for k, v in THESIS_TYPE_BY_CODE.items()}


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AccessStatus(str, Enum):
    """Whether a thesis PDF is publicly downloadable."""

    OPEN = "open"
    RESTRICTED = "restricted"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Thesis:
    """Full thesis record — populated by detail.py or index lookups."""

    # Required identifiers
    kayit_no: str
    tez_no: str

    # Human-visible thesis number (e.g. "T-2024-001")
    thesis_no: str | None = None

    # Bibliographic metadata
    title_tr: str | None = None
    title_en: str | None = None
    author: str | None = None
    advisor: str | None = None
    university: str | None = None
    institute: str | None = None
    department: str | None = None          # ABD — Anabilim Dalı
    science_branch: str | None = None
    thesis_type: str | None = None         # human label, e.g. "Doktora"
    year: int | None = None
    pages: int | None = None
    language: str | None = None

    # Subject / keyword arrays
    subjects: list[str] = field(default_factory=list)
    keywords_tr: list[str] = field(default_factory=list)
    keywords_en: list[str] = field(default_factory=list)

    # Abstracts
    abstract_tr: str | None = None
    abstract_en: str | None = None

    # Access / PDF
    access_status: AccessStatus = AccessStatus.UNKNOWN
    access_reason: str | None = None       # YÖK's stated reason when restricted
    pdf_key: str | None = None             # key for TezGoster endpoint


@dataclass
class SearchHit:
    """Lightweight card row returned from a search result page."""

    kayit_no: str

    tez_no: str | None = None
    thesis_no: str | None = None
    title_tr: str | None = None
    title_en: str | None = None
    author: str | None = None
    year: int | None = None
    university: str | None = None
    thesis_type: str | None = None


@dataclass
class SearchResult:
    """Container for a batch of search hits with coverage metadata."""

    hits: list[SearchHit]
    total_found: int
    shown: int
    coverage_complete: bool
    source: str          # "live" | "index" | "hybrid"
    notes: list[str]
