"""scripts.build_index — polite resumable seed harvester (offline, mocked network)."""
from __future__ import annotations

import asyncio

from yoktez_mcp.models import SearchHit, SearchResult


def _hit(kayit, year=2023):
    return SearchHit(
        kayit_no=kayit, tez_no="t", thesis_no=None, title_tr="T", title_en=None,
        author=None, year=year, university="U", thesis_type="Doktora",
    )


def test_iter_slices_cartesian():
    from scripts.build_index import Slice, iter_slices

    unis = [{"kod": "k", "name": "U", "yoksis_id": "y"}]
    sl = list(iter_slices(unis, ["2"], [2023]))
    assert sl == [Slice(uni=unis[0], tur="2", year=2023)]


def test_iter_slices_multiplies_dims():
    from scripts.build_index import iter_slices

    unis = [{"kod": "k1", "name": "U1", "yoksis_id": "y1"},
            {"kod": "k2", "name": "U2", "yoksis_id": "y2"}]
    sl = list(iter_slices(unis, ["1", "2"], [2022, 2023]))
    assert len(sl) == 2 * 2 * 2


def test_checkpoint_roundtrip(tmp_path):
    from scripts.build_index import Checkpoint

    cp = Checkpoint(tmp_path / "cp.json")
    assert not cp.done("a")
    cp.mark("a")
    # Yeniden yüklenince kalıcı olmalı (resume)
    cp2 = Checkpoint(tmp_path / "cp.json")
    assert cp2.done("a")
    assert not cp2.done("b")


def test_harvest_slice_subdivides_when_capped(monkeypatch):
    from scripts import build_index

    calls = {"n": 0}

    async def fake_adv(**kw):
        calls["n"] += 1
        # Dil filtresi yokken (dil="0") cap'e takılır; Dil bölününce tamamlanır.
        capped = kw.get("dil", "0") == "0"
        return SearchResult(
            hits=[_hit(f"k{calls['n']}")],
            total_found=(3000 if capped else 1),
            shown=(2000 if capped else 1),
            coverage_complete=not capped,
            source="live", notes=[],
        )

    monkeypatch.setattr(build_index.search, "search_advanced", fake_adv)
    sl = build_index.Slice(uni={"kod": "k", "name": "U", "yoksis_id": "y"}, tur="2", year=2023)
    hits, complete = asyncio.run(build_index.harvest_slice(sl))
    assert calls["n"] > 1       # alt-bölme yapıldı (Dil ekseni)
    assert complete is True
    assert hits                 # en az bir hit toplandı


def test_harvest_slice_no_subdivide_when_complete(monkeypatch):
    from scripts import build_index

    calls = {"n": 0}

    async def fake_adv(**kw):
        calls["n"] += 1
        return SearchResult(hits=[_hit("only")], total_found=1, shown=1,
                            coverage_complete=True, source="live", notes=[])

    monkeypatch.setattr(build_index.search, "search_advanced", fake_adv)
    sl = build_index.Slice(uni={"kod": "k", "name": "U", "yoksis_id": "y"}, tur="2", year=2023)
    hits, complete = asyncio.run(build_index.harvest_slice(sl))
    assert calls["n"] == 1      # cap yok → alt-bölme yok
    assert complete is True
    assert len(hits) == 1
