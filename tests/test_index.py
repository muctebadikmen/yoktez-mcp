"""yoktez_mcp.index — FTS5 arama + Türkçe normalizasyon — offline (ağsız).

Bu testler ağ erişimi gerektirmez; sadece bellekte SQLite kullanır.
"""

from __future__ import annotations

import gzip
import shutil

import pytest

from yoktez_mcp import index as idx_mod
from yoktez_mcp.index import SearchIndex, _query_terms
from yoktez_mcp.models import AccessStatus, SearchHit, SearchResult, Thesis
from yoktez_mcp.text import tr_fold

# ---------------------------------------------------------------------------
# Yardımcı: test tezleri
# ---------------------------------------------------------------------------

def _thesis(
    kayit_no: str,
    tez_no: str,
    *,
    title_tr: str | None = None,
    title_en: str | None = None,
    author: str | None = None,
    advisor: str | None = None,
    university: str | None = None,
    institute: str | None = None,
    department: str | None = None,
    thesis_type: str | None = None,
    year: int | None = None,
    keywords_tr: list[str] | None = None,
    keywords_en: list[str] | None = None,
    subjects: list[str] | None = None,
    abstract_tr: str | None = None,
    abstract_en: str | None = None,
    access_status: AccessStatus = AccessStatus.OPEN,
) -> Thesis:
    return Thesis(
        kayit_no=kayit_no,
        tez_no=tez_no,
        title_tr=title_tr,
        title_en=title_en,
        author=author,
        advisor=advisor,
        university=university,
        institute=institute,
        department=department,
        thesis_type=thesis_type,
        year=year,
        keywords_tr=keywords_tr or [],
        keywords_en=keywords_en or [],
        subjects=subjects or [],
        abstract_tr=abstract_tr,
        abstract_en=abstract_en,
        access_status=access_status,
    )


SAMPLE = [
    _thesis(
        "k1", "t1",
        title_tr="İşçi Sağlığı ve İş Güvenliği",
        author="Ayşe Yılmaz",
        advisor="Prof. Dr. Mehmet Öztürk",
        university="Ankara Üniversitesi",
        department="Çalışma Ekonomisi",
        thesis_type="Doktora",
        year=2020,
        keywords_tr=["işçi sağlığı", "iş güvenliği"],
        subjects=["Çalışma Ekonomisi"],
        abstract_tr="Bu tez işçi sağlığı sorunlarını inceler.",
    ),
    _thesis(
        "k2", "t2",
        title_tr="Eğitimde Teknoloji Kullanımı",
        author="Zeynep Kaya",
        advisor="Prof. Dr. Mehmet Öztürk",
        university="Ankara Üniversitesi",
        department="Eğitim Bilimleri",
        thesis_type="Yüksek Lisans",
        year=2022,
        keywords_tr=["eğitim teknolojisi", "dijital öğrenme"],
        subjects=["Eğitim Bilimleri"],
        abstract_tr="Dijital araçların eğitimdeki yeri incelenmektedir.",
    ),
    _thesis(
        "k3", "t3",
        title_tr="Osmanlı Hukuku Tarihi",
        title_en="History of Ottoman Law",
        author="Ali Veli",
        advisor="Doç. Dr. Fatma Şahin",
        university="İstanbul Üniversitesi",
        department="Hukuk",
        thesis_type="Doktora",
        year=2015,
        keywords_tr=["Osmanlı", "hukuk tarihi"],
        keywords_en=["Ottoman", "legal history"],
        subjects=["Hukuk"],
        abstract_tr="Osmanlı dönemi hukuk sistemleri ele alınmaktadır.",
        abstract_en="Ottoman legal systems are examined.",
    ),
]


@pytest.fixture
def idx():
    ix = SearchIndex(":memory:")
    ix.upsert(SAMPLE)
    yield ix
    ix.close()


# ---------------------------------------------------------------------------
# tr_fold simetrisi
# ---------------------------------------------------------------------------

def test_tr_fold_symmetry():
    """İndeks ve sorgu tarafında aynı tr_fold kullanıldığında eşleşme garantisi."""
    assert tr_fold("İŞÇİ") == tr_fold("işçi") == tr_fold("isci") == "isci"
    assert tr_fold("SAĞLIĞI") == tr_fold("sağlığı") == tr_fold("sagligi") == "sagligi"
    assert tr_fold("ÇĞIİÖŞÜ") == "cgiiosu"


def test_indexed_with_folded_variant_query(idx):
    """'İŞÇİ SAĞLIĞI' indekslendi; 'isci sagligi' sorgusu eşleşmeli (fold simetrik)."""
    result = idx.search("isci sagligi")
    ids = {h.kayit_no for h in result.hits}
    assert "k1" in ids


# ---------------------------------------------------------------------------
# _query_terms / stopwords
# ---------------------------------------------------------------------------

def test_query_terms_drop_stopwords():
    assert _query_terms("eğitim ve teknoloji") == ["egitim", "teknoloji"]
    assert _query_terms("ve ile bu") == []


def test_query_terms_turkish_icin():
    # "için" → "icin" → stopword olarak elenmeli
    assert _query_terms("eğitim için politika") == ["egitim", "politika"]


# ---------------------------------------------------------------------------
# upsert + search
# ---------------------------------------------------------------------------

def test_upsert_and_search_returns_searchresult(idx):
    result = idx.search("işçi sağlığı")
    assert isinstance(result, SearchResult)
    assert result.source == "index"
    assert len(result.hits) >= 1
    assert all(isinstance(h, SearchHit) for h in result.hits)


def test_search_exact_title_outranks_body_match():
    """Başlık tam eşleşmesi, sadece özette geçenden üstte sıralamalı."""
    ix = SearchIndex(":memory:")
    ix.upsert([
        _thesis("body_only", "tb", title_tr="Genel Ekonomi",
                abstract_tr="İşçi sağlığı bu çalışmada ele alınmıştır.", year=2020),
        _thesis("title_match", "tt", title_tr="İşçi Sağlığı ve Güvenliği",
                abstract_tr="Farklı bir konu.", year=2018),
    ])
    result = ix.search("işçi sağlığı")
    assert len(result.hits) == 2
    assert result.hits[0].kayit_no == "title_match"
    ix.close()


def test_search_source_is_index(idx):
    result = idx.search("eğitim")
    assert result.source == "index"


def test_search_no_results(idx):
    result = idx.search("xyzxyz_bulunamaz_xyz")
    assert result.hits == []
    assert result.total_found == 0
    assert result.source == "index"


def test_search_empty_query(idx):
    result = idx.search("ve ile")
    assert result.hits == []
    assert result.source == "index"


# ---------------------------------------------------------------------------
# Filtreler
# ---------------------------------------------------------------------------

def test_filter_thesis_type(idx):
    result = idx.search("Ankara", thesis_type="Doktora")
    kayit_nos = {h.kayit_no for h in result.hits}
    assert "k1" in kayit_nos        # Ankara + Doktora
    assert "k2" not in kayit_nos    # Ankara + Yüksek Lisans


def test_filter_year_from(idx):
    result = idx.search("üniversitesi", year_from=2021)
    kayit_nos = {h.kayit_no for h in result.hits}
    assert "k2" in kayit_nos        # 2022 ≥ 2021
    assert "k1" not in kayit_nos    # 2020 < 2021
    assert "k3" not in kayit_nos    # 2015 < 2021


def test_filter_year_to(idx):
    result = idx.search("üniversitesi", year_to=2019)
    kayit_nos = {h.kayit_no for h in result.hits}
    assert "k3" in kayit_nos        # 2015 ≤ 2019
    assert "k1" not in kayit_nos    # 2020 > 2019
    assert "k2" not in kayit_nos    # 2022 > 2019


def test_filter_university(idx):
    result = idx.search("hukuk", university="İstanbul")
    kayit_nos = {h.kayit_no for h in result.hits}
    assert "k3" in kayit_nos
    assert "k1" not in kayit_nos


def test_filter_department(idx):
    result = idx.search("üniversitesi", department="Eğitim")
    kayit_nos = {h.kayit_no for h in result.hits}
    assert "k2" in kayit_nos
    assert "k1" not in kayit_nos


def test_filter_advisor(idx):
    result = idx.search("üniversitesi", advisor="Fatma Şahin")
    kayit_nos = {h.kayit_no for h in result.hits}
    assert "k3" in kayit_nos
    assert "k1" not in kayit_nos


def test_search_limit(idx):
    result = idx.search("üniversitesi", limit=1)
    assert len(result.hits) == 1
    assert result.shown == 1
    assert result.total_found >= 1


# ---------------------------------------------------------------------------
# by_advisor
# ---------------------------------------------------------------------------

def test_by_advisor_finds_theses(idx):
    result = idx.by_advisor("Mehmet Öztürk")
    kayit_nos = {h.kayit_no for h in result.hits}
    assert {"k1", "k2"} == kayit_nos


def test_by_advisor_name_order_tolerant(idx):
    """'Öztürk Mehmet' sorgusu da 'Prof. Dr. Mehmet Öztürk' kaydını bulmalı."""
    result = idx.by_advisor("Öztürk Mehmet")
    kayit_nos = {h.kayit_no for h in result.hits}
    assert {"k1", "k2"} == kayit_nos


def test_by_advisor_fold_insensitive(idx):
    """'mehmet ozturk' gibi fold edilmiş arama da çalışmalı."""
    result = idx.by_advisor("mehmet ozturk")
    kayit_nos = {h.kayit_no for h in result.hits}
    assert {"k1", "k2"} == kayit_nos


def test_by_advisor_source_is_index(idx):
    result = idx.by_advisor("Mehmet Öztürk")
    assert result.source == "index"


def test_by_advisor_no_match(idx):
    result = idx.by_advisor("Yok Biri")
    assert result.hits == []


# ---------------------------------------------------------------------------
# by_author
# ---------------------------------------------------------------------------

def test_by_author_finds_thesis(idx):
    result = idx.by_author("Ayşe Yılmaz")
    kayit_nos = {h.kayit_no for h in result.hits}
    assert "k1" in kayit_nos


def test_by_author_name_order_tolerant(idx):
    """'Yılmaz Ayşe' → 'Ayşe Yılmaz' bulunmalı."""
    result = idx.by_author("Yılmaz Ayşe")
    kayit_nos = {h.kayit_no for h in result.hits}
    assert "k1" in kayit_nos


def test_by_author_source_is_index(idx):
    result = idx.by_author("Zeynep Kaya")
    assert result.source == "index"


# ---------------------------------------------------------------------------
# by_university
# ---------------------------------------------------------------------------

def test_by_university_finds_theses(idx):
    result = idx.by_university("Ankara")
    kayit_nos = {h.kayit_no for h in result.hits}
    assert {"k1", "k2"} == kayit_nos


def test_by_university_fold_insensitive(idx):
    result = idx.by_university("istanbul universitesi")
    kayit_nos = {h.kayit_no for h in result.hits}
    assert "k3" in kayit_nos


def test_by_university_thesis_type_filter(idx):
    result = idx.by_university("Ankara", thesis_type="Doktora")
    kayit_nos = {h.kayit_no for h in result.hits}
    assert "k1" in kayit_nos
    assert "k2" not in kayit_nos


def test_by_university_year_filter(idx):
    result = idx.by_university("Ankara", year_from=2022)
    kayit_nos = {h.kayit_no for h in result.hits}
    assert "k2" in kayit_nos
    assert "k1" not in kayit_nos


def test_by_university_source_is_index(idx):
    result = idx.by_university("Ankara")
    assert result.source == "index"


# ---------------------------------------------------------------------------
# related
# ---------------------------------------------------------------------------

def test_related_finds_shared_subject(idx):
    """k1 (Çalışma Ekonomisi) + k2 (Eğitim Bilimleri) farklı dept; k1↔k3 hukuk ortak yok.
    k3 (Osmanlı/hukuk) ile ilgili tez aranırsa hukuk konularını paylaşanlar bulunmalı."""
    # k3'ün keywords: Osmanlı, hukuk tarihi — bunları paylaşan başka tez yok; en az boş dönmeli
    # Gerçek related testi için aynı konu/keyword'ü paylaşan tez ekleyelim.
    ix = SearchIndex(":memory:")
    t_src = _thesis("src", "ts", title_tr="Osmanlı Hukuku", keywords_tr=["Osmanlı", "hukuk"],
                    subjects=["Hukuk"], year=2010)
    t_rel = _thesis("rel", "tr", title_tr="İslam Hukuku Tarihi", keywords_tr=["hukuk", "İslam"],
                    subjects=["Hukuk"], year=2012)
    t_unr = _thesis("unr", "tu", title_tr="Fizik Bilimleri", keywords_tr=["fizik"],
                    subjects=["Fen Bilimleri"], year=2020)
    ix.upsert([t_src, t_rel, t_unr])
    result = ix.related(t_src)
    ids = {h.kayit_no for h in result.hits}
    assert "src" not in ids        # kaynak tez kendi listesinde olmaz
    assert "rel" in ids            # ortak konu/keyword
    assert "unr" not in ids        # alakasız
    ix.close()


def test_related_source_is_index(idx):
    result = idx.related(SAMPLE[0])
    assert result.source == "index"


def test_related_excludes_self(idx):
    """İlgili tezler listesi kaynak tezi içermemeli."""
    result = idx.related(SAMPLE[2])  # k3 Osmanlı
    ids = {h.kayit_no for h in result.hits}
    assert "k3" not in ids


# ---------------------------------------------------------------------------
# upsert idempotency
# ---------------------------------------------------------------------------

def test_upsert_idempotent(idx):
    """Aynı tezleri tekrar upsert etmek yinelenen kayıt oluşturmaz."""
    ix = SearchIndex(":memory:")
    ix.upsert(SAMPLE)
    ix.upsert(SAMPLE)   # ikinci kez
    result = ix.search("üniversitesi", limit=100)
    kayit_nos = [h.kayit_no for h in result.hits]
    assert len(kayit_nos) == len(set(kayit_nos))  # tekrar yok


def test_upsert_updates_existing():
    """Aynı kayit_no ile farklı içerik upsert edilince güncellenmeli."""
    ix = SearchIndex(":memory:")
    t1 = _thesis("k99", "t99", title_tr="Eski Başlık", year=2010)
    t2 = _thesis("k99", "t99", title_tr="Yeni Başlık", year=2010)
    ix.upsert([t1])
    ix.upsert([t2])
    result = ix.search("Yeni Başlık")
    assert any(h.kayit_no == "k99" for h in result.hits)
    ix.close()


# ---------------------------------------------------------------------------
# get_default_index — placeholder seed
# ---------------------------------------------------------------------------

def test_get_default_index_placeholder_graceful(tmp_path, monkeypatch):
    """Placeholder seed_index.db.gz (sadece _meta tablosu, tez yok) boş ama
    işlevsel bir indeks döndürmeli; çökmemeli."""
    # Env ile yoktez cache'ini tmp_path'e yönlendir; seed'i paket içindekini göster
    monkeypatch.setenv("YOKTEZ_CACHE_DIR", str(tmp_path / "cache"))
    # seed path'i paket data klasöründeki gerçek placeholder
    seed_path = (
        __import__("yoktez_mcp", fromlist=["__file__"]).__file__
    )
    import pathlib
    seed_path = pathlib.Path(seed_path).parent / "data" / "seed_index.db.gz"

    monkeypatch.setenv("YOKTEZ_SEED_INDEX", str(seed_path))
    monkeypatch.setattr(idx_mod, "_default_index", None)

    try:
        default = idx_mod.get_default_index()
        result = default.search("herhangi bir sorgu")
        assert isinstance(result, SearchResult)
        assert result.hits == []
        assert result.total_found == 0
        assert result.source == "index"
    finally:
        if idx_mod._default_index is not None:
            idx_mod._default_index.close()
        idx_mod._default_index = None


def test_get_default_index_no_seed_empty(tmp_path, monkeypatch):
    """Seed yok → boş indeks döner, çökmez."""
    monkeypatch.setenv("YOKTEZ_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("YOKTEZ_SEED_INDEX", str(tmp_path / "yok.db"))
    monkeypatch.setattr(idx_mod, "_default_index", None)

    try:
        default = idx_mod.get_default_index()
        result = default.search("hukuk")
        assert result.hits == []
        assert result.source == "index"
    finally:
        if idx_mod._default_index is not None:
            idx_mod._default_index.close()
        idx_mod._default_index = None


def test_get_default_index_loads_gzip_seed(tmp_path, monkeypatch):
    """Gerçek tez içeren gzip'd seed → get_default_index() ile yüklenmeli."""
    # Bir seed db oluştur
    seed_db = tmp_path / "seed.db"
    sx = SearchIndex(str(seed_db))
    sx.upsert([
        _thesis("s1", "ts1", title_tr="Hukuk Tarihi Araştırması", year=2018),
    ])
    sx.close()

    # gzip'le
    seed_gz = tmp_path / "seed.db.gz"
    with open(seed_db, "rb") as fi, gzip.open(seed_gz, "wb") as fo:
        shutil.copyfileobj(fi, fo)

    monkeypatch.setenv("YOKTEZ_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("YOKTEZ_SEED_INDEX", str(seed_gz))
    monkeypatch.setattr(idx_mod, "_default_index", None)

    try:
        default = idx_mod.get_default_index()
        result = default.search("hukuk")
        assert len(result.hits) >= 1
        assert result.hits[0].kayit_no == "s1"
        assert result.source == "index"
    finally:
        if idx_mod._default_index is not None:
            idx_mod._default_index.close()
        idx_mod._default_index = None


def test_get_default_index_existing_cache_not_overwritten(tmp_path, monkeypatch):
    """Çalışma dizininde index.db varsa, seed üzerine yazmamalı (yerel veriyi korur)."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True)

    # Önceden var olan thesis_index.db: farklı tez içeriyor
    existing_db = cache_dir / "thesis_index.db"
    ex = SearchIndex(str(existing_db))
    ex.upsert([_thesis("existing", "tex", title_tr="Var Olan Tez", year=2020)])
    ex.close()

    # Seed: farklı tez içeriyor
    seed_db = tmp_path / "seed.db"
    sx = SearchIndex(str(seed_db))
    sx.upsert([_thesis("seed_only", "tsd", title_tr="Seed Tezi", year=2021)])
    sx.close()
    seed_gz = tmp_path / "seed.db.gz"
    with open(seed_db, "rb") as fi, gzip.open(seed_gz, "wb") as fo:
        shutil.copyfileobj(fi, fo)

    monkeypatch.setenv("YOKTEZ_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("YOKTEZ_SEED_INDEX", str(seed_gz))
    monkeypatch.setattr(idx_mod, "_default_index", None)

    try:
        default = idx_mod.get_default_index()
        # Var olan tez hâlâ erişilebilir olmalı
        result = default.search("Var Olan")
        assert any(h.kayit_no == "existing" for h in result.hits)
        # Seed'deki tez index'e girmemeli (üzerine yazılmadı)
        result2 = default.search("Seed Tezi")
        assert not any(h.kayit_no == "seed_only" for h in result2.hits)
    finally:
        if idx_mod._default_index is not None:
            idx_mod._default_index.close()
        idx_mod._default_index = None
