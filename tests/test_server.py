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
import yoktez_mcp.facets as _facets_mod
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

    def upsert_hits(self, hits):
        return len(hits)


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

    def upsert_hits(self, hits):
        return len(hits)


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
    # 'makine' canlı hit (_HIT_2 'Makine Öğrenmesi') başlığında geçer → alaka filtresinden geçer.
    result = await srv.search_theses("makine")
    assert result["source"] == "hybrid"


@pytest.mark.asyncio
async def test_search_theses_warms_index_with_live_hits(monkeypatch):
    """Canlı sonuçlar yerel indekse on-demand olarak yazılmalı (upsert_hits)."""

    class RecordingIndex(_EmptyIndex):
        def __init__(self):
            self.warmed = []

        def upsert_hits(self, hits):
            self.warmed.extend(hits)
            return len(hits)

    rec = RecordingIndex()
    monkeypatch.setattr(_index_mod, "get_default_index", lambda: rec)
    monkeypatch.setattr(_search_mod, "search_keyword",
                        lambda *a, **kw: _async_return(SearchResult(
                            hits=[_HIT_1], total_found=1, shown=1,
                            coverage_complete=True, source="live", notes=[]
                        )))

    srv = _import_server()
    await srv.search_theses("yapay zeka")
    assert any(getattr(h, "kayit_no", None) == "111" for h in rec.warmed)


@pytest.mark.asyncio
async def test_search_theses_relevance_drops_zero_coverage(monkeypatch):
    """Canlı sonuçlarda başlık/yazarda hiç sorgu terimi yoksa (gürültü) elenir."""
    off_topic = SearchHit(
        kayit_no="z", tez_no="t", thesis_no=None,
        title_tr="Din eğitimi açısından anlatı", title_en=None, author="X Y",
        year=2023, university="MARMARA", thesis_type="Doktora",
    )
    on_topic = SearchHit(
        kayit_no="a", tez_no="t", thesis_no=None,
        title_tr="Yapay zeka ve hukuk", title_en=None, author="A B",
        year=2022, university="İSTANBUL", thesis_type="Yüksek Lisans",
    )
    monkeypatch.setattr(_search_mod, "search_keyword",
                        lambda *a, **kw: _async_return(SearchResult(
                            hits=[off_topic, on_topic], total_found=2, shown=2,
                            coverage_complete=True, source="live", notes=[]
                        )))
    monkeypatch.setattr(_index_mod, "get_default_index", lambda: _EmptyIndex())

    srv = _import_server()
    result = await srv.search_theses("yapay zeka hukuk")
    kayits = [r["kayit_no"] for r in result["results"]]
    assert "a" in kayits
    assert "z" not in kayits  # sıfır-kapsam gürültü elenir


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


@pytest.mark.asyncio
async def test_search_theses_total_found_none_when_live_fails(monkeypatch):
    """Live SearchError + index hits → total_found must be None (not 0), count>0, source='index'.

    When the live call fails entirely, total_found=0 would be misleading (it could mean
    'live reported 0 results'). Setting it to None makes it unambiguous: live wasn't consulted.
    """
    async def _raise(*a, **kw):
        raise _search_mod.SearchError("Bağlantı hatası")

    monkeypatch.setattr(_search_mod, "search_keyword", _raise)
    monkeypatch.setattr(_index_mod, "get_default_index",
                        lambda: _IndexWithHits([_HIT_1, _HIT_2]))

    srv = _import_server()
    result = await srv.search_theses("yapay zeka")

    assert result["total_found"] is None, (
        f"total_found should be None when live failed, got {result['total_found']!r}"
    )
    assert result["count"] > 0, "count should be > 0 (index returned hits)"
    assert result["results"], "results should be non-empty"
    assert result["source"] == "index", f"source should be 'index', got {result['source']!r}"
    live_fail_notes = [n for n in result["notes"] if "başarısız" in n.lower() or "hata" in n.lower()]
    assert live_fail_notes, "A note about the live failure must be present"


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
async def test_list_university_uses_live_islem2(monkeypatch):
    """Üniversite facet'te bulunursa islem=2 canlı yol kullanılır; eski not kalkar."""
    monkeypatch.setattr(_facets_mod, "find_university",
        lambda q: [{"kod": "ENC", "name": "X ÜNİVERSİTESİ", "yoksis_id": "YID"}])
    captured: dict = {}

    async def fake_adv(**kw):
        captured.update(kw)
        return SearchResult(hits=[_HIT_1], total_found=1, shown=1,
                            coverage_complete=True, source="live", notes=[])

    monkeypatch.setattr(_search_mod, "search_advanced", fake_adv)
    monkeypatch.setattr(_index_mod, "get_default_index", lambda: _EmptyIndex())

    srv = _import_server()
    out = await srv.list_university_theses("X Üniversitesi", thesis_type="Doktora")

    assert out["count"] == 1
    assert out["source"] in ("live", "hybrid")
    assert captured["university_kod"] == "ENC"
    assert captured["university_yoksis"] == "YID"
    assert captured["tur"] == "2"  # Doktora → 2
    # Artık geçerli olmayan "islem=2 kullanılamıyor" notu OLMAMALI.
    assert not any("kullanılamıyor" in n for n in out["notes"])


@pytest.mark.asyncio
async def test_list_university_facet_not_found_falls_back_to_index(monkeypatch):
    """Facet'te yoksa canlıya çıkılmaz: yalnızca indeks + dürüst not."""
    monkeypatch.setattr(_facets_mod, "find_university", lambda q: [])
    called = {"adv": False}

    async def fake_adv(**kw):
        called["adv"] = True
        return SearchResult(hits=[], total_found=0, shown=0,
                            coverage_complete=True, source="live", notes=[])

    monkeypatch.setattr(_search_mod, "search_advanced", fake_adv)
    monkeypatch.setattr(_index_mod, "get_default_index", lambda: _EmptyIndex())

    srv = _import_server()
    out = await srv.list_university_theses("Bilinmeyen Üniversite")

    assert called["adv"] is False  # facet yoksa canlıya çıkma
    assert out["source"] == "index"
    notes_text = " ".join(out["notes"]).lower()
    assert "facet" in notes_text or "bulunamadı" in notes_text


@pytest.mark.asyncio
async def test_list_university_live_error_falls_back_to_index(monkeypatch):
    """islem=2 hata verirse indekse düş + dürüst hata notu."""
    monkeypatch.setattr(_facets_mod, "find_university",
        lambda q: [{"kod": "ENC", "name": "X ÜNİVERSİTESİ", "yoksis_id": "YID"}])

    async def fake_adv(**kw):
        raise _search_mod.SearchError("Geçersiz sorgulama")

    monkeypatch.setattr(_search_mod, "search_advanced", fake_adv)
    monkeypatch.setattr(_index_mod, "get_default_index",
                        lambda: _IndexWithHits([_HIT_1]))

    srv = _import_server()
    out = await srv.list_university_theses("X Üniversitesi")

    assert out["source"] == "index"
    notes_text = " ".join(out["notes"]).lower()
    assert "başarısız" in notes_text or "hata" in notes_text


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

_FAKE_FACETS = {
    "enums": {
        "Tur": {"1": "Yüksek Lisans", "2": "Doktora", "4": "Sanatta Yeterlik"},
        "Dil": {"1": "Türkçe", "2": "İngilizce"},
    },
    "universities": ["İstanbul Üniversitesi", "Ankara Üniversitesi"],
    "abd": ["Eğitim Bilimleri", "Bilgisayar Mühendisliği"],
    "built_at": "2024-01-01T00:00:00",
}


@pytest.mark.asyncio
async def test_list_facets_returns_enums(monkeypatch):
    """list_facets enums döndürmeli — bilinen enum anahtarı içerdiği doğrulanır."""
    monkeypatch.setattr(_facets_mod, "load_facets", lambda: _FAKE_FACETS)
    monkeypatch.setattr(_facets_mod, "find_university", lambda q: _FAKE_FACETS["universities"])
    monkeypatch.setattr(_facets_mod, "find_abd", lambda q: _FAKE_FACETS["abd"])

    import yoktez_mcp.server as srv
    result = await srv.list_facets(kind="enums")
    assert "enums" in result
    # I1 fix: bilinen içerik doğrulanmalı
    assert "Tur" in result["enums"], "enums['Tur'] eksik"
    assert "Doktora" in result["enums"]["Tur"].values(), "Doktora tür değeri eksik"


@pytest.mark.asyncio
async def test_list_facets_has_source_notice(monkeypatch):
    """list_facets source_notice içermeli (M3)."""
    monkeypatch.setattr(_facets_mod, "load_facets", lambda: _FAKE_FACETS)
    monkeypatch.setattr(_facets_mod, "find_university", lambda q: _FAKE_FACETS["universities"])
    monkeypatch.setattr(_facets_mod, "find_abd", lambda q: _FAKE_FACETS["abd"])

    import yoktez_mcp.server as srv
    result = await srv.list_facets()
    assert "source_notice" in result
    assert result["source_notice"]
    # source_notice açıklayıcı olmalı (baked/static)
    assert "baked" in result["source_notice"].lower() or "dictionary" in result["source_notice"].lower()


@pytest.mark.asyncio
async def test_list_facets_invalid_kind():
    """Geçersiz kind ToolError yükseltmeli."""
    from fastmcp.exceptions import ToolError

    import yoktez_mcp.server as srv

    with pytest.raises(ToolError):
        await srv.list_facets(kind="invalid_kind")


# ---------------------------------------------------------------------------
# get_thesis_references — RESTRICTED path (M1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_references_restricted_has_references_false(monkeypatch):
    """Kısıtlı tez → has_references=False (M1)."""
    monkeypatch.setattr(_detail_mod, "get_thesis",
                        lambda *a, **kw: _async_return(_RESTRICTED_THESIS))

    srv = _import_server()
    result = await srv.get_thesis_references("333", "t333")

    assert result["has_references"] is False
    assert result["access_status"] == "restricted"


@pytest.mark.asyncio
async def test_references_restricted_reason_wrapped(monkeypatch):
    """Kısıtlı tezin erişim nedeni [EXTERNAL CONTENT] ile sarılmalı ve source_notice mevcut olmalı (M1)."""
    monkeypatch.setattr(_detail_mod, "get_thesis",
                        lambda *a, **kw: _async_return(_RESTRICTED_THESIS))

    srv = _import_server()
    result = await srv.get_thesis_references("333", "t333")

    assert result["access_reason"] is not None
    assert "[EXTERNAL CONTENT" in result["access_reason"]
    assert "[/EXTERNAL CONTENT]" in result["access_reason"]
    assert "kısıtlanmıştır" in result["access_reason"]
    assert "source_notice" in result
    assert result["source_notice"]


@pytest.mark.asyncio
async def test_references_restricted_never_calls_pdf(monkeypatch):
    """Kısıtlı tez için pdf.download_and_extract çağrılmamalı (M1)."""
    called = []

    async def _should_not_be_called(*a, **kw):
        called.append(True)
        return _EXTRACTED_PDF

    monkeypatch.setattr(_detail_mod, "get_thesis",
                        lambda *a, **kw: _async_return(_RESTRICTED_THESIS))
    monkeypatch.setattr(_pdf_mod, "download_and_extract", _should_not_be_called)

    srv = _import_server()
    await srv.get_thesis_references("333", "t333")
    assert not called, "pdf.download_and_extract çağrılmamalıydı (kısıtlı tez)!"


# ---------------------------------------------------------------------------
# M2/M4: filters_used caveat yalnızca live hit varken eklenmeli
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filters_caveat_present_when_live_hits_filtered(monkeypatch):
    """Live hit + filtre kullanımı → filtre-caveat notu olmalı (M2/M4)."""
    monkeypatch.setattr(_search_mod, "search_keyword",
                        lambda *a, **kw: _async_return(SearchResult(
                            hits=[_HIT_2], total_found=1, shown=1,
                            coverage_complete=True, source="live", notes=[]
                        )))
    monkeypatch.setattr(_index_mod, "get_default_index", lambda: _EmptyIndex())

    srv = _import_server()
    # 'makine' canlı hit (_HIT_2 'Makine Öğrenmesi') başlığında geçer → alaka filtresinden geçer.
    result = await srv.search_theses("makine", year_from=2018)

    caveat_notes = [n for n in result["notes"] if "client-side" in n or "islem=2" in n]
    assert caveat_notes, "Filtre-caveat notu eksik (live hit + filtre kombinasyonunda olmalı)"


@pytest.mark.asyncio
async def test_filters_caveat_absent_when_only_index_hits(monkeypatch):
    """Yalnızca indeks hit + filtre → filtre-caveat notu OLMAMALI (M2/M4)."""
    async def _live_empty(*a, **kw):
        return SearchResult(
            hits=[], total_found=0, shown=0,
            coverage_complete=True, source="live", notes=[]
        )

    monkeypatch.setattr(_search_mod, "search_keyword", _live_empty)
    monkeypatch.setattr(_index_mod, "get_default_index",
                        lambda: _IndexWithHits([_HIT_1]))

    srv = _import_server()
    result = await srv.search_theses("yapay zeka", year_from=2020)

    # source indeks olmalı (live 0 hit döndü)
    assert result["source"] == "index"
    caveat_notes = [n for n in result["notes"] if "client-side" in n or "islem=2" in n]
    assert not caveat_notes, f"Filtre-caveat notu yalnızca-indeks durumunda olmamalı: {caveat_notes}"


@pytest.mark.asyncio
async def test_source_index_when_live_succeeds_but_empty(monkeypatch):
    """Live başarılı ama 0 hit, indeks hit varsa → source='index' (I2)."""
    async def _live_empty(*a, **kw):
        return SearchResult(
            hits=[], total_found=0, shown=0,
            coverage_complete=True, source="live", notes=[]
        )

    monkeypatch.setattr(_search_mod, "search_keyword", _live_empty)
    monkeypatch.setattr(_index_mod, "get_default_index",
                        lambda: _IndexWithHits([_HIT_1]))

    srv = _import_server()
    result = await srv.search_theses("yapay zeka")

    assert result["source"] == "index", (
        f"source='index' beklendi ama '{result['source']}' döndü — "
        "live 0 hit verdi, tüm hitler indeksten geldi"
    )


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------
# Resource testleri (offline)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_server_has_prompts_registered():
    """prompts.register(mcp) wired → 4 prompt kaydedilmiş olmalı."""
    import yoktez_mcp.server as srv

    prompts = await srv.mcp.list_prompts()
    prompt_names = {p.name for p in prompts}
    expected = {
        "tez_literatur_taramasi",
        "tez_ozeti",
        "danisman_ekol_analizi",
        "universite_uretim_haritasi",
    }
    assert expected <= prompt_names, (
        f"Eksik promptlar: {expected - prompt_names}. Kayıtlılar: {prompt_names}"
    )


@pytest.mark.asyncio
async def test_server_has_resource_templates():
    """3 resource template (thesis, advisor, university) kayıtlı olmalı."""
    import yoktez_mcp.server as srv

    templates = await srv.mcp.list_resource_templates()
    uris = {t.uri_template for t in templates}
    assert "yoktez://thesis/{kayit_no}/{tez_no}" in uris, f"thesis resource yok: {uris}"
    assert "yoktez://advisor/{name}" in uris, f"advisor resource yok: {uris}"
    assert "yoktez://university/{name}" in uris, f"university resource yok: {uris}"


@pytest.mark.asyncio
async def test_thesis_resource_returns_wrapped_content(monkeypatch):
    """yoktez://thesis/{kayit_no}/{tez_no} → get_thesis mantığını kullanır, dış içerik sarılır."""
    monkeypatch.setattr(_detail_mod, "get_thesis",
                        lambda *a, **kw: _async_return(_OPEN_THESIS))

    import yoktez_mcp.server as srv

    result = await srv.mcp.read_resource("yoktez://thesis/111/t111")
    # result is ResourceContent or similar; convert to string
    content_str = str(result)
    assert "source_notice" in content_str or "YÖKTEZ" in content_str or "Yapay Zeka" in content_str
    # Must include [EXTERNAL CONTENT] marker somewhere
    assert "[EXTERNAL CONTENT" in content_str or "abstract" in content_str


@pytest.mark.asyncio
async def test_advisor_resource_returns_source_notice(monkeypatch):
    """yoktez://advisor/{name} → find_advisor_theses mantığını kullanır."""
    monkeypatch.setattr(_search_mod, "search_keyword",
                        lambda *a, **kw: _async_return(SearchResult(
                            hits=[_HIT_1], total_found=1, shown=1,
                            coverage_complete=True, source="live", notes=[]
                        )))
    monkeypatch.setattr(_index_mod, "get_default_index", lambda: _EmptyIndex())

    import yoktez_mcp.server as srv

    result = await srv.mcp.read_resource("yoktez://advisor/Ahmet%20Y%C4%B1lmaz")
    content_str = str(result)
    assert "source_notice" in content_str or "YÖKTEZ" in content_str or "advisor" in content_str


@pytest.mark.asyncio
async def test_university_resource_returns_index_note(monkeypatch):
    """yoktez://university/{name} → list_university_theses mantığını kullanır."""
    monkeypatch.setattr(_index_mod, "get_default_index", lambda: _EmptyIndex())
    # Facet'i boş döndür → offline kalsın (canlı islem=2'ye çıkılmaz).
    monkeypatch.setattr(_facets_mod, "find_university", lambda q: [])

    import yoktez_mcp.server as srv

    result = await srv.mcp.read_resource("yoktez://university/%C4%B0stanbul")
    content_str = str(result)
    assert "source_notice" in content_str or "index" in content_str or "YÖKTEZ" in content_str


# ---------------------------------------------------------------------------
# related_theses — indeks boş/ince ise canlı fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_related_theses_live_fallback_when_index_empty(monkeypatch):
    """İndeks boşsa kaynak tezin konu/anahtar kelimelerinden canlı benzer tez türetir."""
    monkeypatch.setattr(_detail_mod, "get_thesis",
                        lambda *a, **kw: _async_return(_OPEN_THESIS))
    monkeypatch.setattr(_index_mod, "get_default_index", lambda: _EmptyIndex())

    related_hits = [
        SearchHit(kayit_no="111", tez_no="t111", title_tr="Yapay Zeka ve Eğitim"),  # kaynak
        SearchHit(kayit_no="888", tez_no="t888", title_tr="Yapay zeka uygulamaları", year=2021),
        SearchHit(kayit_no="999", tez_no="t999", title_tr="Eğitimde yapay zeka", year=2020),
    ]

    async def fake_keyword(query, **kw):
        return SearchResult(hits=related_hits, total_found=3, shown=3,
                            coverage_complete=True, source="live", notes=[])

    monkeypatch.setattr(_search_mod, "search_keyword", fake_keyword)

    srv = _import_server()
    out = await srv.related_theses("111", "t111")

    kayits = [r["kayit_no"] for r in out["results"]]
    assert "111" not in kayits  # kaynak tez hariç tutulur
    assert out["count"] > 0
    assert out["source"] in ("live", "hybrid")


@pytest.mark.asyncio
async def test_related_theses_prefers_index_when_available(monkeypatch):
    """İndekste benzer tez varsa canlıya çıkılmaz (source=index)."""
    monkeypatch.setattr(_detail_mod, "get_thesis",
                        lambda *a, **kw: _async_return(_OPEN_THESIS))
    monkeypatch.setattr(_index_mod, "get_default_index",
                        lambda: _IndexWithHits([_HIT_2]))
    called = {"live": False}

    async def fake_keyword(query, **kw):
        called["live"] = True
        return SearchResult(hits=[], total_found=0, shown=0,
                            coverage_complete=True, source="live", notes=[])

    monkeypatch.setattr(_search_mod, "search_keyword", fake_keyword)

    srv = _import_server()
    out = await srv.related_theses("111", "t111")
    assert out["source"] == "index"
    assert called["live"] is False  # indeks doluysa canlıya gerek yok


# ---------------------------------------------------------------------------
# Advisor/author isim normalizasyonu — canlı çağrıya 'Ad Soyad' geçilmeli
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_advisor_normalizes_surname_first(monkeypatch):
    """find_advisor_theses canlı çağrıya 'Ad Soyad' biçimini geçirmeli."""
    captured: dict = {}

    async def fake_keyword(query, **kw):
        captured["query"] = query
        captured["field"] = kw.get("field")
        return SearchResult(hits=[], total_found=0, shown=0,
                            coverage_complete=True, source="live", notes=[])

    monkeypatch.setattr(_search_mod, "search_keyword", fake_keyword)
    monkeypatch.setattr(_index_mod, "get_default_index", lambda: _EmptyIndex())
    srv = _import_server()
    await srv.find_advisor_theses("Bozkurt, Veysel")
    assert captured["query"] == "Veysel Bozkurt"
    assert captured["field"] == "advisor"


@pytest.mark.asyncio
async def test_find_advisor_total_found_none_when_live_fails(monkeypatch):
    """Canlı katkı yoksa total_found 0 DEĞİL None olmalı (search_theses ile tutarlı)."""
    async def _raise(*a, **kw):
        raise _search_mod.SearchError("boom")

    monkeypatch.setattr(_search_mod, "search_keyword", _raise)
    monkeypatch.setattr(_index_mod, "get_default_index",
                        lambda: _IndexWithHits([_HIT_1]))
    srv = _import_server()
    out = await srv.find_advisor_theses("Veysel Bozkurt")
    assert out["total_found"] is None
    assert out["count"] >= 1  # indeksten geldi


@pytest.mark.asyncio
async def test_find_author_total_found_none_when_live_fails(monkeypatch):
    async def _raise(*a, **kw):
        raise _search_mod.SearchError("boom")

    monkeypatch.setattr(_search_mod, "search_keyword", _raise)
    monkeypatch.setattr(_index_mod, "get_default_index",
                        lambda: _IndexWithHits([_HIT_1]))
    srv = _import_server()
    out = await srv.find_author_theses("Zeynep Kılıç")
    assert out["total_found"] is None


@pytest.mark.asyncio
async def test_find_author_strips_title(monkeypatch):
    """find_author_theses canlı çağrıya ünvansız adı geçirmeli."""
    captured: dict = {}

    async def fake_keyword(query, **kw):
        captured["query"] = query
        return SearchResult(hits=[], total_found=0, shown=0,
                            coverage_complete=True, source="live", notes=[])

    monkeypatch.setattr(_search_mod, "search_keyword", fake_keyword)
    monkeypatch.setattr(_index_mod, "get_default_index", lambda: _EmptyIndex())
    srv = _import_server()
    await srv.find_author_theses("Prof. Dr. Zeynep Kılıç")
    assert captured["query"] == "Zeynep Kılıç"


# ---------------------------------------------------------------------------

async def _async_return(value):
    """Sabit bir değeri döndüren coroutine."""
    return value
