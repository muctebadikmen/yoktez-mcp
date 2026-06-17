"""yoktez_mcp.coverage — 2000-cap'i aşan eksiksiz toplama (offline, mocked + 1 live)."""
from __future__ import annotations

import asyncio

import pytest

from yoktez_mcp.models import SearchHit, SearchResult


def _res(hits, complete=True, total=None):
    return SearchResult(
        hits=hits, total_found=(total if total is not None else len(hits)),
        shown=len(hits), coverage_complete=complete, source="live", notes=[],
    )


def _hit(k, year=2023):
    return SearchHit(kayit_no=k, tez_no="t", thesis_no=None, title_tr="T",
                     title_en=None, author=None, year=year, university="U", thesis_type="Doktora")


def test_year_slices_and_collects_all(monkeypatch):
    from yoktez_mcp import coverage

    seen = []

    async def fake_adv(**kw):
        seen.append(kw["year_from"])
        return _res([_hit(f"{kw['year_from']}-a"), _hit(f"{kw['year_from']}-b")])

    monkeypatch.setattr(coverage.search, "search_advanced", fake_adv)
    hits, complete, reqs = asyncio.run(coverage.collect_all_advanced(
        university_kod="K", university_yoksis="Y", university_name="U",
        tur="2", year_from=2021, year_to=2023))
    assert complete is True
    assert reqs == 3                  # bir sorgu / yıl
    assert len(hits) == 6             # 3 yıl × 2 hit
    assert seen == ["2021", "2022", "2023"]


def test_capped_year_subdivides_by_dil(monkeypatch):
    from yoktez_mcp import coverage

    calls = {"n": 0}

    async def fake_adv(**kw):
        calls["n"] += 1
        # Dil filtresi yokken (dil="0") yalnızca 2023 capped; Dil ile tamamlanır.
        capped = kw.get("dil", "0") == "0" and kw["year_from"] == "2023"
        return _res([_hit(f"{kw['year_from']}-d{kw.get('dil','0')}-{calls['n']}")],
                    complete=not capped, total=(5000 if capped else 1))

    monkeypatch.setattr(coverage.search, "search_advanced", fake_adv)
    hits, complete, reqs = asyncio.run(coverage.collect_all_advanced(
        university_kod="K", university_yoksis="Y", university_name="U",
        tur="2", year_from=2022, year_to=2023))
    assert complete is True
    assert reqs > 2                   # 2023 Dil ekseninde alt-bölündü
    assert hits


def test_respects_max_requests_bound(monkeypatch):
    from yoktez_mcp import coverage

    async def fake_adv(**kw):
        return _res([_hit(kw["year_from"])])

    monkeypatch.setattr(coverage.search, "search_advanced", fake_adv)
    hits, complete, reqs = asyncio.run(coverage.collect_all_advanced(
        university_kod="K", university_yoksis="Y", university_name="U",
        tur="2", year_from=2000, year_to=2050, max_requests=5))
    assert reqs <= 5
    assert complete is False          # sınır nedeniyle tüm yıllar taranamadı


def test_dedupes_across_years(monkeypatch):
    from yoktez_mcp import coverage

    async def fake_adv(**kw):
        return _res([_hit("shared", year=2021)])  # her yıl aynı kayit_no

    monkeypatch.setattr(coverage.search, "search_advanced", fake_adv)
    hits, complete, reqs = asyncio.run(coverage.collect_all_advanced(
        university_kod="K", university_yoksis="Y", university_name="U",
        tur="2", year_from=2020, year_to=2023))
    assert len(hits) == 1


@pytest.mark.live
async def test_collect_all_advanced_beats_cap_live():
    """Canlı: İstanbul Doktora 2015-2022 tek sorguda 2000-cap'e takılır;
    exhaustive yıl-dilimleme cap'i aşar (>2000 benzersiz tez)."""
    from yoktez_mcp import coverage, facets

    uni = sorted(facets.find_university("İstanbul Üniversitesi"), key=lambda u: len(u["name"]))[0]
    hits, complete, reqs = await coverage.collect_all_advanced(
        university_kod=uni["kod"], university_yoksis=uni["yoksis_id"],
        university_name=uni["name"], tur="2", year_from=2015, year_to=2022,
    )
    assert len(hits) > 2000   # tek-sorgu cap'i (2000) aşıldı
    assert complete is True
    assert reqs >= 8          # yıl başına en az bir sorgu
