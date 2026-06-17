"""Tests for yoktez_mcp.search — offline (fixture-based) + one live marker.

Run offline only: uv run pytest tests/test_search.py -m "not live" -v
"""
from __future__ import annotations

import pytest

from yoktez_mcp.search import SearchError, parse_results, search_keyword

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

FIXTURE_BASE = "tests/fixtures"


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# parse_results — results_islem4.html (5 cards, 2000-cap)
# ---------------------------------------------------------------------------


class TestParseResultsIslem4:
    HTML = _read(f"{FIXTURE_BASE}/derived/results_islem4.html")

    def test_hit_count_at_least_five(self):
        result = parse_results(self.HTML)
        assert len(result.hits) >= 5

    def test_known_kayit_no_present(self):
        result = parse_results(self.HTML)
        kayit_nos = [h.kayit_no for h in result.hits]
        # index=0 card from the fixture
        assert "WenFEepJgOInK8Rs_AekDQ" in kayit_nos

    def test_total_found(self):
        result = parse_results(self.HTML)
        # fixture: "Arama sonucunda 2.059 kayıt bulundu."
        assert result.total_found == 2059

    def test_shown(self):
        result = parse_results(self.HTML)
        # fixture: "2.000 tanesi görüntülenmektedir."
        assert result.shown == 2000

    def test_coverage_complete_false_when_capped(self):
        result = parse_results(self.HTML)
        # shown (2000) < total_found (2059) → not complete
        assert result.coverage_complete is False

    def test_source_is_live(self):
        result = parse_results(self.HTML)
        assert result.source == "live"

    def test_first_hit_author_from_reference_data(self):
        result = parse_results(self.HTML)
        hit0 = next(h for h in result.hits if h.kayit_no == "WenFEepJgOInK8Rs_AekDQ")
        assert hit0.author == "ZEYNEP KILIÇ"

    def test_first_hit_year_from_reference_data(self):
        result = parse_results(self.HTML)
        hit0 = next(h for h in result.hits if h.kayit_no == "WenFEepJgOInK8Rs_AekDQ")
        assert hit0.year == 2026

    def test_first_hit_university_from_yer(self):
        result = parse_results(self.HTML)
        # yer = "FIRAT ÜNİVERSİTESİ / " → university = "FIRAT ÜNİVERSİTESİ"
        hit0 = next(h for h in result.hits if h.kayit_no == "WenFEepJgOInK8Rs_AekDQ")
        assert hit0.university == "FIRAT ÜNİVERSİTESİ"

    def test_first_hit_title_tr(self):
        result = parse_results(self.HTML)
        hit0 = result.hits[0]
        assert hit0.title_tr is not None
        assert "Bitcoin" in hit0.title_tr

    def test_first_hit_title_en(self):
        result = parse_results(self.HTML)
        hit0 = result.hits[0]
        assert hit0.title_en is not None
        assert "Bitcoin" in hit0.title_en

    def test_first_hit_thesis_no(self):
        result = parse_results(self.HTML)
        hit0 = result.hits[0]
        assert hit0.thesis_no == "1009908"

    def test_tez_no_present(self):
        result = parse_results(self.HTML)
        hit0 = result.hits[0]
        assert hit0.tez_no is not None
        assert hit0.tez_no == "LMwGw7OVrLZmxj8ZiPn0BQ"


# ---------------------------------------------------------------------------
# parse_results — results_empty.html (no cards, 0 results)
# ---------------------------------------------------------------------------


class TestParseResultsEmpty:
    HTML = _read(f"{FIXTURE_BASE}/derived/results_empty.html")

    def test_hits_empty_list(self):
        result = parse_results(self.HTML)
        assert result.hits == []

    def test_total_found_zero(self):
        result = parse_results(self.HTML)
        assert result.total_found == 0

    def test_coverage_complete_true_for_zero(self):
        result = parse_results(self.HTML)
        # 0 shown >= 0 total → complete
        assert result.coverage_complete is True


# ---------------------------------------------------------------------------
# parse_results — error page (Geçersiz sorgulama)
# ---------------------------------------------------------------------------


class TestParseResultsErrorPage:
    HTML = _read(f"{FIXTURE_BASE}/faz0/error_gecersiz_sorgulama.html")

    def test_raises_search_error(self):
        with pytest.raises(SearchError):
            parse_results(self.HTML)

    def test_error_message_mentions_gecersiz(self):
        with pytest.raises(SearchError, match="Geçersiz"):
            parse_results(self.HTML)


# ---------------------------------------------------------------------------
# search_keyword — field/match validation
# ---------------------------------------------------------------------------


class TestSearchKeywordValidation:
    @pytest.mark.asyncio
    async def test_invalid_field_raises_value_error(self):
        with pytest.raises(ValueError, match="field"):
            await search_keyword("test", field="invalid")

    @pytest.mark.asyncio
    async def test_invalid_match_raises_value_error(self):
        with pytest.raises(ValueError, match="match"):
            await search_keyword("test", match="fuzzy")


# ---------------------------------------------------------------------------
# search_keyword — POST data shape (monkeypatch post_form)
# ---------------------------------------------------------------------------


class TestSearchKeywordPostShape:
    """Verify search_keyword builds the correct POST data dict."""

    @pytest.mark.asyncio
    async def test_post_data_title_contains(self, monkeypatch):
        """field=title, match=contains → nevi=1, tip=2, islem=4."""
        captured: dict = {}

        async def fake_post_form(endpoint: str, data: dict):
            captured.update(data)
            # Return an object with .text
            class FakeResp:
                text = _read(f"{FIXTURE_BASE}/derived/results_islem4.html")
            return FakeResp()

        monkeypatch.setattr("yoktez_mcp.search.post_form", fake_post_form)
        await search_keyword("yapay zeka", field="title", match="contains")

        assert captured["nevi"] == "1"
        assert captured["tip"] == "2"
        assert captured["islem"] == "4"
        assert captured["keyword"] == "yapay zeka"
        # izin/Tur/yil must NOT be present
        assert "izin" not in captured
        assert "Tur" not in captured
        assert "yil1" not in captured
        assert "yil2" not in captured

    @pytest.mark.asyncio
    async def test_post_data_advisor_exact(self, monkeypatch):
        """field=advisor, match=exact → nevi=3, tip=1."""
        captured: dict = {}

        async def fake_post_form(endpoint: str, data: dict):
            captured.update(data)
            class FakeResp:
                text = _read(f"{FIXTURE_BASE}/derived/results_islem4.html")
            return FakeResp()

        monkeypatch.setattr("yoktez_mcp.search.post_form", fake_post_form)
        await search_keyword("Ahmet Yıldız", field="advisor", match="exact")

        assert captured["nevi"] == "3"
        assert captured["tip"] == "1"

    @pytest.mark.asyncio
    async def test_post_data_all_field(self, monkeypatch):
        """field=all → nevi=7."""
        captured: dict = {}

        async def fake_post_form(endpoint: str, data: dict):
            captured.update(data)
            class FakeResp:
                text = _read(f"{FIXTURE_BASE}/derived/results_islem4.html")
            return FakeResp()

        monkeypatch.setattr("yoktez_mcp.search.post_form", fake_post_form)
        await search_keyword("dil", field="all")

        assert captured["nevi"] == "7"

    @pytest.mark.asyncio
    async def test_returns_search_result(self, monkeypatch):
        """search_keyword returns a SearchResult with hits."""
        async def fake_post_form(endpoint: str, data: dict):
            class FakeResp:
                text = _read(f"{FIXTURE_BASE}/derived/results_islem4.html")
            return FakeResp()

        monkeypatch.setattr("yoktez_mcp.search.post_form", fake_post_form)
        result = await search_keyword("yapay zeka")

        assert len(result.hits) >= 5
        assert result.source == "live"


# ---------------------------------------------------------------------------
# Live test (network required)
# ---------------------------------------------------------------------------


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_search_keyword_yapay_zeka():
    """Live: search_keyword('yapay zeka') returns hits with non-empty kayit_no."""
    result = await search_keyword("yapay zeka")
    assert len(result.hits) > 0
    for hit in result.hits:
        assert hit.kayit_no, "kayit_no must not be empty"
