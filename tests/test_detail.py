"""Tests for yoktez_mcp.detail — offline (fixture-based) + one live marker.

Run offline only: uv run pytest tests/test_detail.py -m "not live" -v
"""
from __future__ import annotations

from pathlib import Path

import pytest

from yoktez_mcp.detail import parse_access, parse_detail
from yoktez_mcp.models import AccessStatus

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures" / "faz0"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# parse_detail — izinli (open) thesis
# ---------------------------------------------------------------------------


class TestParseDetailIzinli:
    """tezBilgiDetay.json — FIRAT ÜNİVERSİTESİ bitcoin thesis (izinli)."""

    DATA = _read("tezBilgiDetay.json")

    @pytest.fixture(autouse=True)
    def result(self):
        self._result = parse_detail(self.DATA)
        return self._result

    def test_advisor_stripped(self):
        """danisman HTML stripped → plain advisor name."""
        assert self._result["advisor"] == "DOÇ. DR. AHMED İHSAN ŞİMŞEK"

    def test_university(self):
        assert self._result["university"] == "FIRAT ÜNİVERSİTESİ"

    def test_institute(self):
        assert self._result["institute"] == "SOSYAL BİLİMLER ENSTİTÜSÜ"

    def test_department(self):
        assert self._result["department"] == "İŞLETME ANABİLİM DALI"

    def test_science_branch(self):
        assert self._result["science_branch"] == "İşletme Bilim Dalı"

    def test_abstract_tr_non_empty(self):
        assert self._result["abstract_tr"] is not None
        assert "bitcoin" in self._result["abstract_tr"].lower()

    def test_abstract_en_non_empty(self):
        assert self._result["abstract_en"] is not None
        assert "bitcoin" in self._result["abstract_en"].lower()

    def test_keywords_tr_list(self):
        # Both fixtures have empty keyword HTML → empty list
        assert isinstance(self._result["keywords_tr"], list)

    def test_keywords_en_list(self):
        assert isinstance(self._result["keywords_en"], list)

    def test_server_citations_has_five_keys(self):
        sc = self._result["server_citations"]
        assert set(sc.keys()) == {"apa", "ieee", "mla", "chicago", "harvard"}

    def test_server_citations_apa_non_empty(self):
        assert self._result["server_citations"]["apa"]

    def test_server_citations_ieee_non_empty(self):
        assert self._result["server_citations"]["ieee"]


# ---------------------------------------------------------------------------
# parse_detail — izinsiz (restricted) thesis
# ---------------------------------------------------------------------------


class TestParseDetailIzinsiz:
    """tezBilgiDetay_izinsiz.json — İSTANBUL KÜLTÜR ÜNİV thesis (izinsiz, 2001)."""

    DATA = _read("tezBilgiDetay_izinsiz.json")

    @pytest.fixture(autouse=True)
    def result(self):
        self._result = parse_detail(self.DATA)
        return self._result

    def test_advisor_present(self):
        assert self._result["advisor"] == "PROF. DR. HASAN KARATAŞ"

    def test_university(self):
        assert self._result["university"] == "İSTANBUL KÜLTÜR ÜNİVERSİTESİ"

    def test_institute(self):
        assert self._result["institute"] == "FEN BİLİMLERİ ENSTİTÜSÜ"

    def test_department(self):
        assert self._result["department"] == "İNŞAAT MÜHENDİSLİĞİ ANABİLİM DALI"

    def test_science_branch_none_when_missing(self):
        """izinsiz fixture has only 3 yer parts — science_branch must be None."""
        assert self._result["science_branch"] is None

    def test_abstract_tr_none_when_empty(self):
        """Empty string in JSON → None (honesty: never fabricate)."""
        assert self._result["abstract_tr"] is None

    def test_abstract_en_none_when_empty(self):
        assert self._result["abstract_en"] is None

    def test_keywords_tr_empty_list(self):
        assert self._result["keywords_tr"] == []

    def test_keywords_en_empty_list(self):
        assert self._result["keywords_en"] == []

    def test_server_citations_has_five_keys(self):
        sc = self._result["server_citations"]
        assert set(sc.keys()) == {"apa", "ieee", "mla", "chicago", "harvard"}

    def test_server_citations_apa_non_empty(self):
        assert self._result["server_citations"]["apa"]


# ---------------------------------------------------------------------------
# parse_access — izinli fragment
# ---------------------------------------------------------------------------


class TestParseAccessIzinli:
    HTML = _read("getTezPdf_card0.html")

    def test_status_open(self):
        status, reason, key = parse_access(self.HTML)
        assert status == AccessStatus.OPEN

    def test_reason_none(self):
        _, reason, _ = parse_access(self.HTML)
        assert reason is None

    def test_pdf_key_non_empty(self):
        _, _, key = parse_access(self.HTML)
        assert key is not None
        assert len(key) > 0

    def test_pdf_key_exact(self):
        """Key must match the exact token from the fixture."""
        _, _, key = parse_access(self.HTML)
        assert key == "5T1_CZ5-UGb9QCmoURec4BEPAinYCKRPkksMGIbw70WFzh6rSp8zhkeqaI8qq_5m"


# ---------------------------------------------------------------------------
# parse_access — izinsiz fragment
# ---------------------------------------------------------------------------


class TestParseAccessIzinsiz:
    HTML = _read("getTezPdf_izinsiz.html")
    EXPECTED_REASON = (
        "Bu tezin, veri tabanı üzerinden yayınlanma izni bulunmamaktadır. "
        "Yayınlanma izni olmayan tezlerin basılı kopyalarına Üniversite kütüphaneniz "
        "aracılığıyla (TÜBESS üzerinden) erişebilirsiniz."
    )

    def test_status_restricted(self):
        status, _, _ = parse_access(self.HTML)
        assert status == AccessStatus.RESTRICTED

    def test_pdf_key_none(self):
        _, _, key = parse_access(self.HTML)
        assert key is None

    def test_reason_exact_text(self):
        """Verbatim YÖK restriction reason — never fabricated."""
        _, reason, _ = parse_access(self.HTML)
        assert reason == self.EXPECTED_REASON

    def test_reason_non_empty(self):
        _, reason, _ = parse_access(self.HTML)
        assert reason is not None and reason.strip()


# ---------------------------------------------------------------------------
# parse_access — unknown fragment (neither open nor restricted)
# ---------------------------------------------------------------------------


class TestParseAccessUnknown:
    def test_empty_html_returns_unknown(self):
        status, reason, key = parse_access("<div></div>")
        assert status == AccessStatus.UNKNOWN
        assert reason is None
        assert key is None


# ---------------------------------------------------------------------------
# get_thesis — monkeypatched (offline)
# ---------------------------------------------------------------------------


class TestGetThesisOffline:
    """get_thesis should merge parse_detail + parse_access + base_meta."""

    @pytest.mark.asyncio
    async def test_get_thesis_open(self, monkeypatch):
        """Open thesis: access_status OPEN, pdf_key set, advisor populated."""
        from yoktez_mcp.detail import get_thesis
        from yoktez_mcp.models import SearchHit

        detail_json = _read("tezBilgiDetay.json")
        pdf_html = _read("getTezPdf_card0.html")

        async def fake_get_text(url: str, params=None) -> str:
            if "tezBilgiDetay" in url:
                return detail_json
            if "getTezPdf" in url:
                return pdf_html
            raise AssertionError(f"Unexpected URL: {url}")

        monkeypatch.setattr("yoktez_mcp.detail.get_text", fake_get_text)

        base = SearchHit(
            kayit_no="WenFEepJgOInK8Rs_AekDQ",
            tez_no="LMwGw7OVrLZmxj8ZiPn0BQ",
            title_tr="Makine öğrenmesi algoritmaları ile Bitcoin fiyat tahmini",
            author="ZEYNEP KILIÇ",
            year=2026,
            thesis_type="Yüksek Lisans",
        )

        thesis = await get_thesis(
            "WenFEepJgOInK8Rs_AekDQ", "LMwGw7OVrLZmxj8ZiPn0BQ", base_meta=base
        )

        assert thesis.kayit_no == "WenFEepJgOInK8Rs_AekDQ"
        assert thesis.tez_no == "LMwGw7OVrLZmxj8ZiPn0BQ"
        assert thesis.access_status == AccessStatus.OPEN
        assert thesis.pdf_key == "5T1_CZ5-UGb9QCmoURec4BEPAinYCKRPkksMGIbw70WFzh6rSp8zhkeqaI8qq_5m"
        assert thesis.advisor == "DOÇ. DR. AHMED İHSAN ŞİMŞEK"
        assert thesis.abstract_tr is not None
        assert thesis.author == "ZEYNEP KILIÇ"
        assert thesis.year == 2026

    @pytest.mark.asyncio
    async def test_get_thesis_restricted(self, monkeypatch):
        """Restricted thesis: access_status RESTRICTED, access_reason set, no pdf_key."""
        from yoktez_mcp.detail import get_thesis

        detail_json = _read("tezBilgiDetay_izinsiz.json")
        pdf_html = _read("getTezPdf_izinsiz.html")

        async def fake_get_text(url: str, params=None) -> str:
            if "tezBilgiDetay" in url:
                return detail_json
            if "getTezPdf" in url:
                return pdf_html
            raise AssertionError(f"Unexpected URL: {url}")

        monkeypatch.setattr("yoktez_mcp.detail.get_text", fake_get_text)

        thesis = await get_thesis("SOMEKAYIT", "SOMETEZNO")

        assert thesis.access_status == AccessStatus.RESTRICTED
        assert thesis.pdf_key is None
        assert thesis.access_reason is not None
        assert "izni bulunmamaktadır" in thesis.access_reason
        assert thesis.abstract_tr is None
        assert thesis.abstract_en is None
        assert thesis.advisor == "PROF. DR. HASAN KARATAŞ"


# ---------------------------------------------------------------------------
# Live test
# ---------------------------------------------------------------------------


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_get_thesis_open():
    """Live: known open thesis (kayitNo from faz0 fixture card0) → OPEN + pdf_key set."""
    from yoktez_mcp.detail import get_thesis

    # card0 from faz0 fixtures: WenFEepJgOInK8Rs_AekDQ / LMwGw7OVrLZmxj8ZiPn0BQ
    thesis = await get_thesis(
        "WenFEepJgOInK8Rs_AekDQ",
        "LMwGw7OVrLZmxj8ZiPn0BQ",
    )

    assert thesis.access_status == AccessStatus.OPEN, (
        f"Expected OPEN but got {thesis.access_status}; "
        f"access_reason={thesis.access_reason!r}"
    )
    assert thesis.pdf_key, "pdf_key must be non-empty for an open thesis"
    assert thesis.advisor, "advisor must be populated from tezBilgiDetay.jsp"
