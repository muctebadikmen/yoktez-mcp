"""Tests for shared models — Task 1."""
from __future__ import annotations

from yoktez_mcp.models import (
    THESIS_TYPE_BY_CODE,
    THESIS_TYPE_TO_CODE,
    AccessStatus,
    SearchHit,
    SearchResult,
    Thesis,
)

# ---------------------------------------------------------------------------
# THESIS_TYPE_BY_CODE / THESIS_TYPE_TO_CODE
# ---------------------------------------------------------------------------

class TestThesisTypeMaps:
    def test_code3_is_tipta_uzmanlik(self):
        assert THESIS_TYPE_BY_CODE["3"] == "Tıpta Uzmanlık"

    def test_all_seven_codes_present(self):
        assert set(THESIS_TYPE_BY_CODE.keys()) == {"1", "2", "3", "4", "5", "6", "7"}

    def test_expected_labels(self):
        assert THESIS_TYPE_BY_CODE["1"] == "Yüksek Lisans"
        assert THESIS_TYPE_BY_CODE["2"] == "Doktora"
        assert THESIS_TYPE_BY_CODE["4"] == "Sanatta Yeterlik"
        assert THESIS_TYPE_BY_CODE["5"] == "Diş Hekimliği Uzmanlık"
        assert THESIS_TYPE_BY_CODE["6"] == "Tıpta Yan Dal Uzmanlık"
        assert THESIS_TYPE_BY_CODE["7"] == "Eczacılıkta Uzmanlık"

    def test_inverse_round_trip(self):
        """Every code in BY_CODE must round-trip through TO_CODE."""
        for code, label in THESIS_TYPE_BY_CODE.items():
            assert THESIS_TYPE_TO_CODE[label] == code

    def test_inverse_has_same_length(self):
        assert len(THESIS_TYPE_TO_CODE) == len(THESIS_TYPE_BY_CODE)


# ---------------------------------------------------------------------------
# AccessStatus
# ---------------------------------------------------------------------------

class TestAccessStatus:
    def test_values(self):
        assert AccessStatus.OPEN == "open"
        assert AccessStatus.RESTRICTED == "restricted"
        assert AccessStatus.UNKNOWN == "unknown"

    def test_is_str(self):
        assert isinstance(AccessStatus.OPEN, str)


# ---------------------------------------------------------------------------
# Thesis dataclass
# ---------------------------------------------------------------------------

class TestThesis:
    def test_required_fields_only(self):
        """Thesis can be constructed with only kayit_no and tez_no."""
        t = Thesis(kayit_no="12345", tez_no="67890")
        assert t.kayit_no == "12345"
        assert t.tez_no == "67890"

    def test_optional_fields_default_to_none(self):
        t = Thesis(kayit_no="1", tez_no="2")
        assert t.title_tr is None
        assert t.title_en is None
        assert t.author is None
        assert t.advisor is None
        assert t.university is None
        assert t.institute is None
        assert t.department is None
        assert t.science_branch is None
        assert t.thesis_type is None
        assert t.year is None
        assert t.pages is None
        assert t.language is None
        assert t.abstract_tr is None
        assert t.abstract_en is None
        assert t.access_reason is None
        assert t.pdf_key is None
        assert t.thesis_no is None

    def test_list_fields_default_to_empty_list(self):
        t = Thesis(kayit_no="1", tez_no="2")
        assert t.subjects == []
        assert t.keywords_tr == []
        assert t.keywords_en == []

    def test_access_status_defaults_to_unknown(self):
        t = Thesis(kayit_no="1", tez_no="2")
        assert t.access_status == AccessStatus.UNKNOWN

    def test_full_construction(self):
        t = Thesis(
            kayit_no="100",
            tez_no="200",
            thesis_no="TZ-2024-001",
            title_tr="Örnek Tez Başlığı",
            title_en="Sample Thesis Title",
            author="Ahmet Yılmaz",
            advisor="Prof. Dr. Ayşe Kara",
            university="Ankara Üniversitesi",
            institute="Fen Bilimleri Enstitüsü",
            department="Bilgisayar Mühendisliği",
            science_branch="Yapay Zeka",
            thesis_type="Doktora",
            year=2024,
            pages=150,
            language="Türkçe",
            subjects=["Yapay Zeka", "Makine Öğrenimi"],
            keywords_tr=["derin öğrenme", "sinir ağı"],
            keywords_en=["deep learning", "neural network"],
            abstract_tr="Türkçe özet.",
            abstract_en="English abstract.",
            access_status=AccessStatus.OPEN,
            access_reason=None,
            pdf_key="abc123",
        )
        assert t.year == 2024
        assert t.pages == 150
        assert t.access_status == AccessStatus.OPEN
        assert t.subjects == ["Yapay Zeka", "Makine Öğrenimi"]

    def test_list_fields_are_independent(self):
        """Mutable defaults must not be shared between instances."""
        t1 = Thesis(kayit_no="1", tez_no="2")
        t2 = Thesis(kayit_no="3", tez_no="4")
        t1.subjects.append("X")
        assert t2.subjects == []


# ---------------------------------------------------------------------------
# SearchHit dataclass
# ---------------------------------------------------------------------------

class TestSearchHit:
    def test_all_optional_except_kayit_no(self):
        hit = SearchHit(kayit_no="999")
        assert hit.kayit_no == "999"
        assert hit.tez_no is None
        assert hit.thesis_no is None
        assert hit.title_tr is None
        assert hit.title_en is None
        assert hit.author is None
        assert hit.year is None
        assert hit.university is None
        assert hit.thesis_type is None

    def test_full_construction(self):
        hit = SearchHit(
            kayit_no="1",
            tez_no="2",
            thesis_no="TZ-001",
            title_tr="Başlık",
            title_en="Title",
            author="Yazar",
            year=2020,
            university="ODTÜ",
            thesis_type="Yüksek Lisans",
        )
        assert hit.year == 2020
        assert hit.thesis_type == "Yüksek Lisans"


# ---------------------------------------------------------------------------
# SearchResult dataclass
# ---------------------------------------------------------------------------

class TestSearchResult:
    def test_minimal_construction(self):
        sr = SearchResult(
            hits=[],
            total_found=0,
            shown=0,
            coverage_complete=True,
            source="live",
            notes=[],
        )
        assert sr.hits == []
        assert sr.source == "live"
        assert sr.coverage_complete is True

    def test_with_hits(self):
        hit = SearchHit(kayit_no="42")
        sr = SearchResult(
            hits=[hit],
            total_found=1,
            shown=1,
            coverage_complete=False,
            source="hybrid",
            notes=["cap reached"],
        )
        assert len(sr.hits) == 1
        assert sr.hits[0].kayit_no == "42"
        assert sr.source == "hybrid"
        assert "cap reached" in sr.notes
