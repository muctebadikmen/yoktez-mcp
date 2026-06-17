"""yoktez_mcp.relevance — canlı sonuç alaka filtresi/sıralaması testleri (offline)."""
from __future__ import annotations

from yoktez_mcp.models import SearchHit


def _hit(title, *, year=2020, kayit="k", author=None):
    return SearchHit(
        kayit_no=kayit, tez_no="t", thesis_no=None, title_tr=title,
        title_en=None, author=author, year=year, university=None, thesis_type=None,
    )


def test_drops_hit_missing_a_query_term():
    from yoktez_mcp.relevance import relevance_filter_sort

    hits = [
        _hit("Yapay zeka ile tıpta tanı", kayit="a"),
        _hit("Din eğitimi açısından anlatı", kayit="b"),  # 'yapay/zeka/tıp' yok
    ]
    out = relevance_filter_sort(hits, "yapay zeka tıp")
    kayits = [h.kayit_no for h in out]
    assert "a" in kayits
    assert "b" not in kayits


def test_turkish_fold_symmetric_match():
    from yoktez_mcp.relevance import relevance_filter_sort

    # Sorgu ASCII ('tip'), başlık Türkçe ('tıp') — fold ile eşleşmeli.
    hits = [_hit("Yapay zeka ile tıpta tanı", kayit="a")]
    out = relevance_filter_sort(hits, "yapay zeka tip")
    assert [h.kayit_no for h in out] == ["a"]


def test_orders_full_coverage_before_partial():
    from yoktez_mcp.relevance import relevance_filter_sort

    hits = [
        _hit("Yapay zeka", kayit="partial"),
        _hit("Yapay zeka ile hukuk", kayit="full"),
    ]
    out = relevance_filter_sort(hits, "yapay zeka hukuk", require_all_terms=False)
    assert out[0].kayit_no == "full"


def test_empty_query_returns_all():
    from yoktez_mcp.relevance import relevance_filter_sort

    hits = [_hit("X", kayit="a"), _hit("Y", kayit="b")]
    out = relevance_filter_sort(hits, "ve ile")  # yalnızca stopword
    assert len(out) == 2


def test_matches_terms_in_author_field():
    from yoktez_mcp.relevance import relevance_filter_sort

    hits = [_hit("Bir tez", kayit="a", author="Zeynep Kılıç")]
    out = relevance_filter_sort(hits, "Zeynep Kılıç")
    assert [h.kayit_no for h in out] == ["a"]


def test_min_terms_drops_only_zero_coverage_keeps_partial():
    """min_terms=1: hiç terim içermeyen gürültü elenir, kısmi eşleşme korunur."""
    from yoktez_mcp.relevance import relevance_filter_sort

    hits = [
        _hit("Yapay zeka düzenlemeleri", kayit="partial"),  # 2/3 terim
        _hit("Din eğitimi açısından anlatı", kayit="noise"),  # 0/3 terim
    ]
    out = relevance_filter_sort(hits, "yapay zeka tıp", require_all_terms=False, min_terms=1)
    kayits = [h.kayit_no for h in out]
    assert "partial" in kayits
    assert "noise" not in kayits
