"""server.py için offline (monkeypatched) testler.

Ağa çıkılmaz — search.search_keyword, detail.get_thesis,
pdf.download_and_extract, index.get_default_index monkeypatched.

Kapsam:
  - search_theses: kayıt yapısı, source/coverage, year_from filtresi, dedupe
  - get_thesis: zengin kayıt + 8 atıf, abstrakt sarma
  - get_thesis_fulltext: kısıtlı → PDF yok, OPEN → metin + sarma
  - list_university_theses: boş indeks → dürüst not
  - EXTERNAL CONTENT sarma: marker + source_notice varlığı
"""

from __future__ import annotations

import pytest

import yoktez_mcp.detail as _detail_mod
import yoktez_mcp.index as _index_mod
import yoktez_mcp.pdf as _pdf_mod
import yoktez_mcp.search as _search_mod
from yoktez_mcp.models import (
    AccessStatus,
    SearchHit,
    SearchResult,
    Thesis,
)
from yoktez_mcp.pdf import ExtractedPDF

# ---------------------------------------------------------------------------
# Fixture nesneleri
# ---------------------------------------------------------------------------

_HIT_1 = SearchHit(
    kayit_no="111",
    tez_no="t111",
    thesis_no="100001",
    title_tr="Yapay Zeka ve Eğitim",
    title_en="Artificial Intelligence and Education",
    author="Zeynep Kılıç",
    year=2022,
    university="İSTANBUL ÜNİVERSİTESİ",
    thesis_type="Doktora",
)

_HIT_2 = SearchHit(
    kayit_no="222",
    tez_no="t222",
    thesis_no="100002",
    title_tr="Makine Öğrenmesi",
    title_en="Machine Learning",
    author="Ali Demir",
    year=2019,
    university="ANKARA ÜNİVERSİTESİ",
    thesis_type="Yüksek Lisans",
)

_HIT_DUP = SearchHit(
    kayit_no="111",  # duplicate kayit_no
    tez_no="t111",
    title_tr="Yapay Zeka ve Eğitim",
    author="Zeynep Kılıç",
    year=2022,
    university="İSTANBUL ÜNİVERSİTESİ",
    thesis_type="Doktora",
)

_LIVE_RESULT_FULL = SearchResult(
    hits=[_HIT_1, _HIT_2],
    total_found=2,
    shown=2,
    coverage_complete=True,
    source="live",
    notes=[],
)

_LIVE_RESULT_CAPPED = SearchResult(
    hits=[_HIT_1],
    total_found=5000,
    shown=1,
    coverage_complete=False,
    source="live",
    notes=[],
)

_OPEN_THESIS = Thesis(
    kayit_no="111",
    tez_no="t111",
    thesis_no="100001",
    title_tr="Yapay Zeka ve Eğitim",
    title_en="Artificial Intelligence and Education",
    author="Zeynep Kılıç",
    advisor="Prof. Dr. Ahmet Yılmaz",
    university="İSTANBUL ÜNİVERSİTESİ",
    institute="Eğitim Bilimleri Enstitüsü",
    department="Eğitim Teknolojisi",
    thesis_type="Doktora",
    year=2022,
    abstract_tr="Bu tez yapay zeka uygulamalarını inceler.",
    abstract_en="This thesis examines AI applications.",
    keywords_tr=["yapay zeka", "eğitim"],
    keywords_en=["AI", "education"],
    access_status=AccessStatus.OPEN,
    access_reason=None,
    pdf_key="abc123",
)

_RESTRICTED_THESIS = Thesis(
    kayit_no="333",
    tez_no="t333",
    thesis_no="100003",
    title_tr="Gizli Tez",
    author="Mehmet Şahin",
    university="EGE ÜNİVERSİTESİ",
    thesis_type="Yüksek Lisans",
    year=2020,
    abstract_tr=None,  # kısıtlıysa özet boş gelir
    abstract_en=None,
    access_status=AccessStatus.RESTRICTED,
    access_reason="Bu tez yayın hakkı nedeniyle kısıtlanmıştır.",
    pdf_key=None,
)

_EXTRACTED_PDF = ExtractedPDF(
    source_url="https://tez.yok.gov.tr/UlusalTezMerkezi/TezGoster?key=abc123",
    page_count=120,
    pages=["Giriş metni buradadır..."],
    markdown="# Tam metin\n\nGiriş metni buradadır...",
    has_text=True,
    text_reliable=True,
    note=None,
    sections=[
        {"heading": "GİRİŞ", "text": "Giriş metni."},
        {"heading": "KAYNAKÇA", "text": "Yazar A. (2020). Makale adı."},
    ],
    start_page=1,
    end_page=120,
    has_more_pages=False,
)


# ---------------------------------------------------------------------------
# Yardımcı: boş SearchResult döndüren SearchIndex mock'u
# ---------------------------------------------------------------------------

class _EmptyIndex:
    """by_university / by_advisor / by_author / search / related her zaman boş döndürür."""

    def search(self, query, **kwargs):
        return SearchResult(
            hits=[], total_found=0, shown=0,
            coverage_complete=True, source="index", notes=[]
        )

    def by_advisor(self, name, **kwargs):
        return SearchResult(
            hits=[], total_found=0, shown=0,
            coverage_complete=True, source="index", notes=[]
        )

    def by_author(self, name, **kwargs):
        return SearchResult(
            hits=[], total_found=0, shown=0,
            coverage_complete=True, source="index", notes=[]
        )

    def by_university(self, name, **kwargs):
        return SearchResult(
            hits=[], total_found=0, shown=0,
            coverage_complete=True, source="index", notes=[]
        )

    def related(self, thesis, **kwargs):
        return SearchResult(
            hits=[], total_found=0, shown=0,
            coverage_complete=True, source="index", notes=[]
        )


class _IndexWithHits:
    """Sabit hit listesi döndüren mock."""

    def __init__(self, hits):
        self._hits = hits

    def search(self, query, **kwargs):
        return SearchResult(
            hits=self._hits[:],
            total_found=len(self._hits),
            shown=len(self._hits),
            coverage_complete=True, source="index", notes=[]
        )

    def by_advisor(self, name, **kwargs):
        return SearchResult(
            hits=self._hits[:],
            total_found=len(self._hits),
            shown=len(self._hits),
            coverage_complete=True, source="index", notes=[]
        )

    def by_author(self, name, **kwargs):
        return SearchResult(
            hits=self._hits[:],
            total_found=len(self._hits),
            shown=len(self._hits),
            coverage_complete=True, source="index", notes=[]
        )

    def by_university(self, name, **kwargs):
        return SearchResult(
            hits=self._hits[:],
            total_found=len(self._hits),
            shown=len(self._hits),
            coverage_complete=True, source="index", notes=[]
        )

    def related(self, thesis, **kwargs):
        return SearchResult(
            hits=self._hits[:],
            total_found=len(self._hits),
            shown=len(self._hits),
            coverage_complete=True, source="index", notes=[]
        )


# ---------------------------------------------------------------------------
# server modülünü geç import (monkeypatch için)
# ---------------------------------------------------------------------------

def _import_server():
    """server modülünü import eder. Testlerde her çağrıda taze modül."""
    import yoktez_mcp.server as srv
    return srv


# ---------------------------------------------------------------------------
# search_theses testleri
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_theses_returns_required_fields(monkeypatch):
    """search_theses temel dict yapısını döndürmeli."""
    monkeypatch.setattr(_search_mod, "search_keyword",
                        lambda *a, **kw: _async_return(_LIVE_RESULT_FULL))
    monkeypatch.setattr(_index_mod, "get_default_index", lambda: _EmptyIndex())

    srv = _import_server()
    result = await srv.search_theses("yapay zeka")

    assert "results" in result
    assert "source" in result
    assert "coverage_complete" in result
    assert "notes" in result
    assert "source_notice" in result
    assert result["source_notice"]  # boş değil


@pytest.mark.asyncio
async def test_search_theses_coverage_complete_true(monkeypatch):
    """coverage_complete=True iken notlarda 2000-cap uyarısı olmamalı."""
    monkeypatch.setattr(_search_mod, "search_keyword",
                        lambda *a, **kw: _async_return(_LIVE_RESULT_FULL))
    monkeypatch.setattr(_index_mod, "get_default_index", lambda: _EmptyIndex())

    srv = _import_server()
    result = await srv.search_theses("eğitim")

    cap_notes = [n for n in result["notes"] if "2000-cap" in n]
    assert not cap_notes


@pytest.mark.asyncio
async def test_search_theses_coverage_complete_false_adds_note(monkeypatch):
    """coverage_complete=False iken 2000-cap notu olmalı."""
    monkeypatch.setattr(_search_mod, "search_keyword",
                        lambda *a, **kw: _async_return(_LIVE_RESULT_CAPPED))
    monkeypatch.setattr(_index_mod, "get_default_index", lambda: _EmptyIndex())

    srv = _import_server()
    result = await srv.search_theses("eğitim")

    assert result["coverage_complete"] is False
    cap_notes = [n for n in result["notes"] if "2000-cap" in n]
    assert cap_notes


@pytest.mark.asyncio
async def test_search_theses_year_from_filters(monkeypatch):
    """year_from filtresi eski tezleri ekmeli."""
    monkeypatch.setattr(_search_mod, "search_keyword",
                        lambda *a, **kw: _async_return(_LIVE_RESULT_FULL))
    monkeypatch.setattr(_index_mod, "get_default_index", lambda: _EmptyIndex())

    srv = _import_server()
    result = await srv.search_theses("yapay zeka", year_from=2021)

    years = [r["year"] for r in result["results"] if r["year"] is not None]
    assert all(y >= 2021 for y in years)
    # HIT_2 (2019) elenmiş, HIT_1 (2022) kalmış
    kayit_nos = {r["kayit_no"] for r in result["results"]}
    assert "111" in kayit_nos
    assert "222" not in kayit_nos


@pytest.mark.asyncio
async def test_search_theses_dedupes_by_kayit_no(monkeypatch):
    """Aynı kayit_no hem index hem live'dan gelirse tek kez görünmeli."""
    # İndeks de HIT_1 döndürüyor, live de HIT_1 döndürüyor
    monkeypatch.setattr(_search_mod, "search_keyword",
                        lambda *a, **kw: _async_return(SearchResult(
                            hits=[_HIT_DUP], total_found=1, shown=1,
                            coverage_complete=True, source="live", notes=[]
                        )))
    monkeypatch.setattr(_index_mod, "get_default_index",
                        lambda: _IndexWithHits([_HIT_1]))

    srv = _import_server()
    result = await srv.search_theses("yapay zeka")

    kayit_nos = [r["kayit_no"] for r in result["results"]]
    # 111 yalnızca bir kez görünmeli
    assert kayit_nos.count("111") == 1


@pytest.mark.asyncio
async def test_search_theses_source_hybrid(monkeypatch):
    """Hem indeks hem live hit varsa source='hybrid' olmalı."""
    monkeypatch.setattr(_search_mod, "search_keyword",
                        lambda *a, **kw: _async_return(SearchResult(
                            hits=[_HIT_2], total_found=1, shown=1,
                            coverage_complete=True, source="live", notes=[]
                        )))
    monkeypatch.setattr(_index_mod, "get_default_index",
                        lambda: _IndexWithHits([_HIT_1]))

    srv = _import_server()
    result = await srv.search_theses("zeka")
    assert result["source"] == "hybrid"


@pytest.mark.asyncio
async def test_search_theses_source_live_when_index_empty(monkeypatch):
    """Yalnızca live hit varsa source='live' olmalı."""
    monkeypatch.setattr(_search_mod, "search_keyword",
                        lambda *a, **kw: _async_return(_LIVE_RESULT_FULL))
    monkeypatch.setattr(_index_mod, "get_default_index", lambda: _EmptyIndex())

    srv = _import_server()
    result = await srv.search_theses("zeka")
    assert result["source"] == "live"


@pytest.mark.asyncio
async def test_search_theses_live_error_falls_back_to_index(monkeypatch):
    """Canlı arama hatası verse de (örn. SearchError) index sonuçları döner."""
    async def _raise(*a, **kw):
        raise _search_mod.SearchError("Geçersiz sorgulama")

    monkeypatch.setattr(_search_mod, "search_keyword", _raise)
    monkeypatch.setattr(_index_mod, "get_default_index",
                        lambda: _IndexWithHits([_HIT_1]))

    srv = _import_server()
    result = await srv.search_theses("yapay zeka")
    assert result["count"] >= 1
    error_notes = [n for n in result["notes"] if "başarısız" in n.lower()]
    assert error_notes


# ---------------------------------------------------------------------------
# get_thesis testleri
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_thesis_returns_all_citation_keys(monkeypatch):
    """get_thesis 8 atıf formatını döndürmeli."""
    monkeypatch.setattr(_detail_mod, "get_thesis",
                        lambda *a, **kw: _async_return(_OPEN_THESIS))

    srv = _import_server()
    result = await srv.get_thesis("111", "t111")

    assert "citations" in result
    cits = result["citations"]
    for key in ("bibtex", "ris", "csl_json", "apa", "mla", "ieee", "chicago", "harvard"):
        assert key in cits, f"Eksik atıf formatı: {key}"


@pytest.mark.asyncio
async def test_get_thesis_abstract_wrapped(monkeypatch):
    """Abstrakt [EXTERNAL CONTENT] ile sarılmalı."""
    monkeypatch.setattr(_detail_mod, "get_thesis",
                        lambda *a, **kw: _async_return(_OPEN_THESIS))

    srv = _import_server()
    result = await srv.get_thesis("111", "t111")

    assert "[EXTERNAL CONTENT" in result["abstract_tr"]
    assert "[/EXTERNAL CONTENT]" in result["abstract_tr"]
    assert result["source_notice"]


@pytest.mark.asyncio
async def test_get_thesis_source_notice_present(monkeypatch):
    """source_notice her zaman mevcut olmalı."""
    monkeypatch.setattr(_detail_mod, "get_thesis",
                        lambda *a, **kw: _async_return(_OPEN_THESIS))

    srv = _import_server()
    result = await srv.get_thesis("111", "t111")
    assert "source_notice" in result
    assert result["source_notice"]


@pytest.mark.asyncio
async def test_get_thesis_none_abstract_not_wrapped(monkeypatch):
    """Boş abstrakt None olarak kalmalı, sarılmamalı."""
    thesis_no_abstract = Thesis(
        kayit_no="111",
        tez_no="t111",
        access_status=AccessStatus.OPEN,
        abstract_tr=None,
        abstract_en=None,
    )
    monkeypatch.setattr(_detail_mod, "get_thesis",
                        lambda *a, **kw: _async_return(thesis_no_abstract))

    srv = _import_server()
    result = await srv.get_thesis("111", "t111")
    assert result["abstract_tr"] is None
    assert result["abstract_en"] is None


# ---------------------------------------------------------------------------
# get_thesis_fulltext testleri
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fulltext_restricted_returns_reason_not_pdf(monkeypatch):
    """Kısıtlı tez → has_fulltext=False, access_status=restricted, PDF metni YOK."""
    monkeypatch.setattr(_detail_mod, "get_thesis",
                        lambda *a, **kw: _async_return(_RESTRICTED_THESIS))

    srv = _import_server()
    result = await srv.get_thesis_fulltext("333", "t333")

    assert result["has_fulltext"] is False
    assert result["access_status"] == "restricted"
    assert "markdown" not in result


@pytest.mark.asyncio
async def test_fulltext_restricted_never_calls_pdf(monkeypatch):
    """Kısıtlı tez için pdf.download_and_extract çağrılmamalı."""
    called = []

    async def _should_not_be_called(*a, **kw):
        called.append(True)
        return _EXTRACTED_PDF

    monkeypatch.setattr(_detail_mod, "get_thesis",
                        lambda *a, **kw: _async_return(_RESTRICTED_THESIS))
    monkeypatch.setattr(_pdf_mod, "download_and_extract", _should_not_be_called)

    srv = _import_server()
    await srv.get_thesis_fulltext("333", "t333")
    assert not called, "pdf.download_and_extract çağrılmamalıydı (kısıtlı tez)!"


@pytest.mark.asyncio
async def test_fulltext_restricted_reason_wrapped(monkeypatch):
    """Kısıtlı tezin erişim nedeni [EXTERNAL CONTENT] ile sarılmalı."""
    monkeypatch.setattr(_detail_mod, "get_thesis",
                        lambda *a, **kw: _async_return(_RESTRICTED_THESIS))

    srv = _import_server()
    result = await srv.get_thesis_fulltext("333", "t333")

    assert result["access_reason"] is not None
    assert "[EXTERNAL CONTENT" in result["access_reason"]
    assert "[/EXTERNAL CONTENT]" in result["access_reason"]
    assert "kısıtlanmıştır" in result["access_reason"]


@pytest.mark.asyncio
async def test_fulltext_open_returns_markdown_wrapped(monkeypatch):
    """Açık tez için markdown [EXTERNAL CONTENT] ile sarılmalı."""
    monkeypatch.setattr(_detail_mod, "get_thesis",
                        lambda *a, **kw: _async_return(_OPEN_THESIS))
    monkeypatch.setattr(_pdf_mod, "download_and_extract",
                        lambda *a, **kw: _async_return(_EXTRACTED_PDF))

    srv = _import_server()
    result = await srv.get_thesis_fulltext("111", "t111")

    assert result["has_fulltext"] is True
    assert result["text_reliable"] is True
    assert "[EXTERNAL CONTENT" in result["markdown"]
    assert "[/EXTERNAL CONTENT]" in result["markdown"]


@pytest.mark.asyncio
async def test_fulltext_open_sections_present(monkeypatch):
    """Açık tezde sections ToC döner."""
    monkeypatch.setattr(_detail_mod, "get_thesis",
                        lambda *a, **kw: _async_return(_OPEN_THESIS))
    monkeypatch.setattr(_pdf_mod, "download_and_extract",
                        lambda *a, **kw: _async_return(_EXTRACTED_PDF))

    srv = _import_server()
    result = await srv.get_thesis_fulltext("111", "t111")

    assert "sections" in result
    assert isinstance(result["sections"], list)
    # heading + char_count alanları olmalı
    if result["sections"]:
        assert "heading" in result["sections"][0]
        assert "char_count" in result["sections"][0]


# ---------------------------------------------------------------------------
# list_university_theses testleri
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_university_theses_empty_index_honest_note(monkeypatch):
    """Boş indeks → honest not (seed not yet built / unavailable)."""
    monkeypatch.setattr(_index_mod, "get_default_index", lambda: _EmptyIndex())

    srv = _import_server()
    result = await srv.list_university_theses("İstanbul Üniversitesi")

    assert result["total_found"] == 0
    assert result["count"] == 0
    # islem=2 unavailable notu var mı?
    notes_text = " ".join(result["notes"])
    assert "islem=2" in notes_text or "kullanılamıyor" in notes_text or "unavailable" in notes_text
    # seed not built / empty mesajı
    assert "seed" in notes_text or "indeks" in notes_text or "bulunamadı" in notes_text


@pytest.mark.asyncio
async def test_list_university_theses_always_adds_islem2_note(monkeypatch):
    """İndeks doluyken bile islem=2 notu eklenmeli."""
    monkeypatch.setattr(_index_mod, "get_default_index",
                        lambda: _IndexWithHits([_HIT_1]))

    srv = _import_server()
    result = await srv.list_university_theses("İstanbul Üniversitesi")

    notes_text = " ".join(result["notes"])
    assert "islem=2" in notes_text or "kullanılamıyor" in notes_text


# ---------------------------------------------------------------------------
# EXTERNAL CONTENT sarma testleri (genel doğrulama)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_external_content_marker_in_thesis_abstract(monkeypatch):
    """get_thesis'te abstract_tr [EXTERNAL CONTENT] / [/EXTERNAL CONTENT] içermeli."""
    monkeypatch.setattr(_detail_mod, "get_thesis",
                        lambda *a, **kw: _async_return(_OPEN_THESIS))

    srv = _import_server()
    result = await srv.get_thesis("111", "t111")

    assert "[EXTERNAL CONTENT" in result["abstract_tr"]
    assert "[/EXTERNAL CONTENT]" in result["abstract_tr"]


@pytest.mark.asyncio
async def test_external_content_in_fulltext_markdown(monkeypatch):
    """get_thesis_fulltext'te markdown dış içerik işaretli olmalı."""
    monkeypatch.setattr(_detail_mod, "get_thesis",
                        lambda *a, **kw: _async_return(_OPEN_THESIS))
    monkeypatch.setattr(_pdf_mod, "download_and_extract",
                        lambda *a, **kw: _async_return(_EXTRACTED_PDF))

    srv = _import_server()
    result = await srv.get_thesis_fulltext("111", "t111")

    assert "[EXTERNAL CONTENT" in result["markdown"]
    assert "[/EXTERNAL CONTENT]" in result["markdown"]


# ---------------------------------------------------------------------------
# find_advisor_theses / find_author_theses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_advisor_theses_merges_results(monkeypatch):
    """find_advisor_theses hem live hem indeks sonuçlarını birleştirmeli."""
    monkeypatch.setattr(_search_mod, "search_keyword",
                        lambda *a, **kw: _async_return(SearchResult(
                            hits=[_HIT_2], total_found=1, shown=1,
                            coverage_complete=True, source="live", notes=[]
                        )))
    monkeypatch.setattr(_index_mod, "get_default_index",
                        lambda: _IndexWithHits([_HIT_1]))

    srv = _import_server()
    result = await srv.find_advisor_theses("Prof. Dr. Ahmet Yılmaz")

    kayit_nos = {r["kayit_no"] for r in result["results"]}
    assert "111" in kayit_nos
    assert "222" in kayit_nos
    assert result["source"] == "hybrid"


@pytest.mark.asyncio
async def test_find_author_theses_has_source_notice(monkeypatch):
    """find_author_theses source_notice içermeli."""
    monkeypatch.setattr(_search_mod, "search_keyword",
                        lambda *a, **kw: _async_return(_LIVE_RESULT_FULL))
    monkeypatch.setattr(_index_mod, "get_default_index", lambda: _EmptyIndex())

    srv = _import_server()
    result = await srv.find_author_theses("Zeynep Kılıç")

    assert "source_notice" in result
    assert result["source_notice"]


# ---------------------------------------------------------------------------
# list_facets
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_facets_returns_enums():
    """list_facets enums döndürmeli."""
    import yoktez_mcp.server as srv
    result = await srv.list_facets(kind="enums")
    assert "enums" in result


@pytest.mark.asyncio
async def test_list_facets_invalid_kind():
    """Geçersiz kind ToolError yükseltmeli."""
    from fastmcp.exceptions import ToolError

    import yoktez_mcp.server as srv

    with pytest.raises(ToolError):
        await srv.list_facets(kind="invalid_kind")


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------

async def _async_return(value):
    """Sabit bir değeri döndüren coroutine."""
    return value
